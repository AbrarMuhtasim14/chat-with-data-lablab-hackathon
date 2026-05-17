# agents/agents.py
"""
Enterprise Chat-with-Data Pipeline for AtliQ Hospitality.
Architecture: Gemini + Native Function Calling

 ┌──────────────────────────────────────────────────────┐
 │ Gemini receives question + database context          │
 │                        ↓                            │
 │ Gemini natively calls: calculate_metrics({          │
 │   metrics: ["occupancy_pct", "revpar"],             │
 │   filters: {},                                      │
 │   group_by: "category"                              │
 │ })                                                  │
 │                        ↓                            │
 │ Python: Deterministic SQL builder → DB → Data       │
 │                        ↓                            │
 │ Data sent back to Gemini                            │
 │                        ↓                            │
 │ Gemini presents professional business answer        │
 └──────────────────────────────────────────────────────┘
"""

import json
import os
import subprocess
import traceback
import google.generativeai as genai
from tools.tools import (
    execute_multiple_metrics, execute_custom_sql,
    get_database_context, resolve_metric_name
)
from utils.config import (
    GEMINI_API_KEY, GEMINI_MODEL, METRIC_LIBRARY
)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Suppress debug noise
VERBOSE = True


def _log(msg):
    if VERBOSE:
        print(msg)

def _proto_to_dict(obj):
    """Recursively convert Gemini protobuf types to plain Python."""
    if hasattr(obj, 'items'):
        return {k: _proto_to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, '__iter__') and not isinstance(obj, str):
        return [_proto_to_dict(i) for i in obj]
    else:
        return obj


# ════════════════════════════════════════════════
# SYSTEM PROMPT (built with live DB context)
# ════════════════════════════════════════════════

def _build_system_prompt(db_context):
    """Build system prompt with live database context and metric catalog."""
    metric_lines = []
    for key, info in METRIC_LIBRARY.items():
        aliases = info.get('aliases', [])[:3]
        alias_str = f" (also: {', '.join(aliases)})" if aliases else ""
        metric_lines.append(f"  {key}: {info['description']}{alias_str}")
    metric_catalog = "\n".join(metric_lines)

    return f"""You are a data analyst for AtliQ Hospitality, a hotel chain operating in India.
Your job: Answer business questions using the tools provided. Call tools to get data, then
present a professional answer.

DATABASE CONTEXT:
- Date range: {db_context['date_range']}
- Cities: {', '.join(db_context['cities'])}
- Weeks: {db_context['weeks']} (week_no is TEXT — always quote as '31' not 31)
- Latest full week: '{db_context['latest_full_week']}'
- Platforms: {', '.join(db_context['platforms'])}
- Categories: Luxury, Business
- Room classes: Standard, Elite, Premium, Presidential
- day_type: 'Weekend' (Friday & Saturday), 'Weekday' (Sunday to Thursday)

AVAILABLE METRICS (use these exact names in calculate_metrics):
{metric_catalog}

WoW METRICS (pass current_week in filters instead of week_no):
  wow_revenue, wow_occupancy, wow_adr, wow_revpar, wow_realisation, wow_dsrn

HOW TO INTERPRET QUESTIONS:
- "performance" / "snapshot" / "overview" → metrics: [revenue, occupancy_pct, adr, revpar, realisation_pct]
- "filling rooms" / "how full" / "utilization" → metrics: [occupancy_pct]
- "revenue per room" / "yield per room" → metrics: [revpar]
- "conversion" / "bookings to stays" / "checked in" → metrics: [realisation_pct]
- "rate" / "average rate" → metrics: [adr]
- "luxury vs business" / "by category" → group_by: "category"
- "by city" / "across cities" / "per city" → group_by: "city"
- "trend" / "weekly" / "over time" → group_by: "week_no"
- "weekend vs weekday" → group_by: "day_type"
- "by platform" → group_by: "booking_platform"
- "by hotel" / "by property" → group_by: "property_name"
- "compared to last week" / "week over week" → use wow_ metrics with current_week filter
- "latest week" → filter week_no: '{db_context['latest_full_week']}'
- "top N" / "ranking" / "which hotel has highest/lowest" → use run_custom_sql

SCHEMA (for run_custom_sql only):
- fact_bookings (fb): booking_id, property_id, check_in_date, checkout_date, revenue_realized,
  booking_status ('Checked Out'/'Cancelled'/'No Show'), booking_platform, room_category (RT1-RT4),
  ratings_given (0=not rated), no_guests
- fact_aggregated_bookings (fa): property_id, check_in_date, room_category,
  successful_bookings, capacity
- dim_hotels (dh): property_id, property_name, category, city
- dim_date (dd): date, mmm_yy, week_no (TEXT!), day_type
- dim_rooms (dr): room_id, room_class
- Joins: fb/fa.property_id = dh.property_id | fb/fa.check_in_date = dd.date | fb/fa.room_category = dr.room_id
- NEVER direct-join fact_bookings with fact_aggregated_bookings
- revenue_realized = THE revenue column (not revenue_generated)

ANSWER RULES:
- Revenue → ₹X.XXM or ₹X.XXB
- Percentages → XX.X%
- Rates/RevPAR/ADR → ₹X,XXX
- Keep under 200 words
- End with one actionable business insight
- ONLY use numbers from tool results — NEVER invent numbers
"""


# ════════════════════════════════════════════════
# TOOL SCHEMAS (OpenAI Function Calling Format)
# We keep OpenAI format here, then convert to Gemini
# ════════════════════════════════════════════════

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_metrics",
            "description": (
                "Calculate one or more hotel KPIs with optional filters and grouping. "
                "Handles ALL metrics including cross-table ones like RevPAR (uses CTEs automatically). "
                "This is the PRIMARY tool — use it for all standard KPI questions. "
                "You CAN request multiple metrics in one call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of metric names to calculate. Available: "
                            "revenue, total_bookings, adr, average_rating, "
                            "realisation_pct, cancellation_pct, no_show_rate_pct, "
                            "occupancy_pct, total_capacity, total_successful_bookings, "
                            "revpar, dbrn, dsrn, durn, "
                            "booking_pct_by_platform, booking_pct_by_room_class, "
                            "wow_revenue, wow_occupancy, wow_adr, wow_revpar, wow_realisation, wow_dsrn"
                        )
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters to narrow results.",
                        "properties": {
                            "city": {"type": "string", "description": "City name: Delhi, Mumbai, Hyderabad, or Bangalore"},
                            "week_no": {"type": "string", "description": "Week number as TEXT: '19' to '32'"},
                            "category": {"type": "string", "description": "Hotel category: Luxury or Business"},
                            "property_name": {"type": "string", "description": "Exact hotel name"},
                            "day_type": {"type": "string", "description": "'Weekend' (Fri+Sat) or 'Weekday' (Sun-Thu)"},
                            "mmm_yy": {"type": "string", "description": "Month: 'May 22', 'Jun 22', or 'Jul 22'"},
                            "room_class": {"type": "string", "description": "Standard, Elite, Premium, or Presidential"},
                            "booking_platform": {"type": "string", "description": "Booking channel name"},
                            "current_week": {"type": "string", "description": "Current week for WoW metrics"}
                        }
                    },
                    "group_by": {
                        "type": "string",
                        "description": (
                            "Optional: group results by a dimension. "
                            "Options: city, property_name, category, week_no, "
                            "mmm_yy, day_type, room_class, booking_platform"
                        )
                    }
                },
                "required": ["metrics"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_custom_sql",
            "description": (
                "Execute a custom PostgreSQL query for questions that don't map to standard metrics. "
                "Use for: top N rankings, specific record lookups, custom conditions, correlations. "
                "NEVER direct-join fact_bookings with fact_aggregated_bookings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "description": (
                            "A PostgreSQL SELECT or WITH (CTE) query. "
                            "Tables: fact_bookings fb, fact_aggregated_bookings fa, "
                            "dim_hotels dh, dim_date dd, dim_rooms dr. "
                            "Remember: week_no is TEXT — use '31' not 31."
                        )
                    }
                },
                "required": ["sql_query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_metric",
            "description": (
                "Find the correct metric name for a business concept. "
                "Use when you're unsure which metric name to pass to calculate_metrics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "Business concept to search, e.g., 'revenue yield', 'conversion rate'"}
                },
                "required": ["search_term"]
            }
        }
    }
]


# ════════════════════════════════════════════════
# GEMINI TOOL CONVERSION
# ════════════════════════════════════════════════

def _get_gemini_type(openai_type: str):
    """Map OpenAI type strings to Gemini Type enums."""
    type_map = {
        'string': genai.protos.Type.STRING,
        'object': genai.protos.Type.OBJECT,
        'array': genai.protos.Type.ARRAY,
        'number': genai.protos.Type.NUMBER,
        'integer': genai.protos.Type.INTEGER,
        'boolean': genai.protos.Type.BOOLEAN
    }
    return type_map.get(openai_type, genai.protos.Type.STRING)


def _convert_tools_to_gemini(openai_schemas):
    """Convert OpenAI-style tool schemas to Gemini FunctionDeclaration format."""
    gemini_tools = []

    for schema in openai_schemas:
        if schema.get('type') != 'function':
            continue

        func = schema['function']
        properties = {}

        for prop_name, prop_def in func['parameters']['properties'].items():
            prop_type = _get_gemini_type(prop_def.get('type', 'string'))

            prop_schema = genai.protos.Schema(
                type=prop_type,
                description=prop_def.get('description', '')
            )

            # Handle arrays
            if prop_def.get('type') == 'array' and 'items' in prop_def:
                prop_schema = genai.protos.Schema(
                    type=prop_type,
                    description=prop_def.get('description', ''),
                    items=genai.protos.Schema(
                        type=_get_gemini_type(prop_def['items'].get('type', 'string'))
                    )
                )

            # Handle nested objects
            if prop_def.get('type') == 'object' and 'properties' in prop_def:
                nested_props = {}
                for nested_name, nested_def in prop_def['properties'].items():
                    nested_props[nested_name] = genai.protos.Schema(
                        type=_get_gemini_type(nested_def.get('type', 'string')),
                        description=nested_def.get('description', '')
                    )
                prop_schema = genai.protos.Schema(
                    type=prop_type,
                    description=prop_def.get('description', ''),
                    properties=nested_props
                )

            properties[prop_name] = prop_schema

        gemini_func = genai.protos.FunctionDeclaration(
            name=func['name'],
            description=func['description'],
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties=properties,
                required=func['parameters'].get('required', [])
            )
        )

        gemini_tools.append(gemini_func)

    return gemini_tools


# ════════════════════════════════════════════════
# TOOL EXECUTOR
# ════════════════════════════════════════════════

def _execute_tool_call(tool_name, arguments):
    """Execute a tool call and return the result as a string."""
    _log(f"  🔧 Tool: {tool_name}")
    _log(f"  📝 Args: {json.dumps(arguments, indent=2)}")

    try:
        if tool_name == "calculate_metrics":
            metrics = arguments.get("metrics", [])
            filters = arguments.get("filters") or {}
            group_by = arguments.get("group_by")

            # Clean filters
            filters = {
                k: str(v) for k, v in filters.items()
                if v is not None and str(v).strip()
            }

            _log(f"  📊 Metrics: {metrics}")
            _log(f"  🔍 Filters: {filters}")
            _log(f"  📁 Group by: {group_by}")

            results = execute_multiple_metrics(metrics, filters, group_by)

            output_parts = []
            for metric_name, result in results.items():
                if result['error']:
                    output_parts.append(f"❌ {metric_name}: {result['error']}")
                    _log(f"  ❌ {metric_name}: {result['error']}")
                else:
                    row_count = len(result['df']) if result['df'] is not None else 0
                    output_parts.append(f"✅ {metric_name}:\n{result['markdown']}")
                    _log(f"  ✅ {metric_name}: {row_count} rows")

            return "\n\n".join(output_parts) if output_parts else "No results returned."

        elif tool_name == "run_custom_sql":
            sql = arguments.get("sql_query", "")
            _log(f"  🔍 SQL: {sql[:120]}...")
            df, err = execute_custom_sql(sql)
            if err:
                _log(f"  ❌ {err}")
                return f"SQL Error: {err}"
            if df is None or df.empty:
                return "Query returned 0 rows. Check your filter values."
            _log(f"  ✅ {len(df)} rows returned")
            return df.to_markdown(index=False)

        elif tool_name == "search_metric":
            term = arguments.get("search_term", "")
            matches = resolve_metric_name(term)
            if not matches:
                all_metrics = list(METRIC_LIBRARY.keys())
                return f"No metric found for '{term}'. Available metrics: {all_metrics}"
            lines = []
            for key in matches:
                info = METRIC_LIBRARY[key]
                lines.append(f"  {key}: {info['description']}")
            return "Matching metrics:\n" + "\n".join(lines)

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        error_msg = f"Tool execution error: {str(e)}"
        _log(f"  ❌ {error_msg}")
        return error_msg


# ════════════════════════════════════════════════
# LOBSTER TRAP SECURITY LAYER (REAL BINARY)
# ════════════════════════════════════════════════

def _lobster_trap_inspect(question: str) -> dict:
    """
    Inspect prompt using the real Lobster Trap CLI binary if available.

    Expected files at project root:
      - ./lobstertrap
      - ./lobstertrap_policy.yaml   (optional)

    If binary isn't present, we fall back to allow (so the app still works).
    """
    project_root = os.path.dirname(os.path.dirname(__file__))
    binary_path = os.path.join(project_root, "lobstertrap")
    policy_path = os.path.join(project_root, "lobstertrap_policy.yaml")

    if not os.path.exists(binary_path):
        return {"is_safe": True, "risk_score": 0, "reason": "LobsterTrap binary not found (fallback allow)"}

    # Base command: lobstertrap inspect "<question>"
    cmd = [binary_path, "inspect", question]

    # If you have a policy file, use it.
    # LobsterTrap docs mention a default policy YAML at configs/default_policy.yaml. :contentReference[oaicite:2]{index=2}
    if os.path.exists(policy_path):
        cmd = [binary_path, "inspect", "--policy", policy_path, question]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()

        # Treat non-zero exit as blocked; also scan for common deny keywords.
        blocked = (result.returncode != 0) or ("DENY" in output) or ("BLOCK" in output)

        return {
            "is_safe": not blocked,
            "risk_score": 100 if blocked else 0,
            "reason": output if blocked else "Clean",
            "raw_output": output,
        }
    except subprocess.TimeoutExpired:
        return {"is_safe": True, "risk_score": 0, "reason": "LobsterTrap timeout (fallback allow)"}
    except Exception as e:
        return {"is_safe": True, "risk_score": 0, "reason": f"LobsterTrap error: {e} (fallback allow)"}


# ════════════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════════════

def query_data_agent(question: str) -> str:
    """
    Enterprise Chat-with-Data entry point using Gemini.
    Uses native function calling:
    1. Gemini understands question
    2. Gemini calls tools via structured JSON
    3. Python executes tools deterministically
    4. Gemini presents business answer
    """
    _log(f"\n{'='*60}")
    _log(f"❓ QUESTION: {question}")
    _log(f"🤖 Model: {GEMINI_MODEL}")
    _log(f"{'='*60}")

    try:
        # ── Security Check (Lobster Trap) ──
        security_check = _lobster_trap_inspect(question)
        if not security_check['is_safe']:
            _log(f"\n🔒 BLOCKED by Lobster Trap: {security_check['reason']}")
            return (
                f"🔒 **Security Alert**: This query was blocked by our security layer.\n\n"
                f"**Risk Score**: {security_check['risk_score']}/100\n"
                f"**Reason**: {security_check['reason']}\n\n"
                f"Please rephrase your question to focus on hotel analytics."
            )

        # ── Step 1: Load DB context ──
        _log(f"\n📊 Loading database context...")
        db_context = get_database_context()
        if 'error' in db_context:
            return f"Database connection error: {db_context['error']}"
        _log(f"✅ {len(db_context['weeks'])} weeks, {len(db_context['cities'])} cities loaded")

        # ── Step 2: Build system prompt ──
        system_prompt = _build_system_prompt(db_context)

        # ── Step 3: Convert tools to Gemini format ──
        gemini_tool_declarations = _convert_tools_to_gemini(TOOL_SCHEMAS)
        gemini_tools = genai.protos.Tool(
            function_declarations=gemini_tool_declarations
        )

        # ── Step 4: Initialize Gemini model ──
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            tools=[gemini_tools],
            system_instruction=system_prompt
        )

        # ── Step 5: Start chat session ──
        chat = model.start_chat(history=[])

        # ── Step 6: Send initial question ──
        _log(f"\n🔄 LLM Call #1...")
        response = chat.send_message(question)

        # ── Step 7: Agentic loop ──
        max_iterations = 5

        for iteration in range(max_iterations):
            _log(f"\n🔄 Processing iteration #{iteration + 1}...")

            # Check response parts
            if not response.candidates or not response.candidates[0].content.parts:
                break

            parts = response.candidates[0].content.parts
            has_function_call = False
            final_text = None

            for part in parts:
                # Check for function call
                if hasattr(part, 'function_call') and part.function_call.name:
                    has_function_call = True
                    fn_name = part.function_call.name
                    fn_args = _proto_to_dict(part.function_call.args)

                    _log(f"  🔧 Tool called: {fn_name}")

                    # Execute tool
                    result = _execute_tool_call(fn_name, fn_args)

                    # Send result back to Gemini
                    _log(f"\n🔄 Sending tool result back to Gemini...")
                    response = chat.send_message(
                        genai.protos.Content(
                            parts=[genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=fn_name,
                                    response={"result": str(result)}
                                )
                            )]
                        )
                    )
                    break  # Handle one tool call at a time

                # Check for text response (final answer)
                if hasattr(part, 'text') and part.text and part.text.strip():
                    final_text = part.text

            # If we got a final text answer (no tool calls)
            if not has_function_call and final_text:
                _log(f"\n✅ Final answer received ({len(final_text)} chars)")
                return final_text

        # If we exhausted iterations, try to get final text
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text and part.text.strip():
                    return part.text

        return "Analysis could not be completed. Please try rephrasing your question."

    except Exception as e:
        _log(f"\n❌ Pipeline error: {str(e)}")
        _log(traceback.format_exc())
        return f"I encountered an error while processing your question: {str(e)}"