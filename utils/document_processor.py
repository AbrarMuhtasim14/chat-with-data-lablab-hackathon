# utils/document_processor.py
"""
Document Intelligence Module for Track 4.
Extracts entities and knowledge graphs from uploaded PDFs using Gemini.
"""

import io
import json
import PyPDF2
import pdfplumber
import google.generativeai as genai
from typing import Dict, List, Tuple, Optional
from utils.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)


def extract_text_from_pdf(pdf_file) -> str:
    """
    Extract text from uploaded PDF file.
    
    Args:
        pdf_file: Streamlit UploadedFile object
        
    Returns:
        Extracted text as string
    """
    try:
        # Try pdfplumber first (better for tables)
        with pdfplumber.open(pdf_file) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        # Fallback to PyPDF2
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e2:
            raise Exception(f"Failed to extract PDF text: {str(e2)}")


def extract_knowledge_graph(text: str) -> Dict:
    """
    Use Gemini to extract structured knowledge graph from document text.
    
    Args:
        text: Document text
        
    Returns:
        Dict with entities, relationships, and benchmarks
    """
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    prompt = f"""You are analyzing a hospitality industry document. Extract structured information as JSON.

Document text:
{text[:10000]}  # Limit to first 10k chars

Extract the following:

1. **Entities** - List of hotels, cities, brands, or properties mentioned
2. **KPIs** - Any metrics mentioned (occupancy %, ADR, RevPAR, revenue, etc.)
3. **Benchmarks** - Industry averages or competitor numbers
4. **Insights** - Key findings or recommendations
5. **Relationships** - How entities relate (e.g., "Hotel X outperforms Hotel Y in RevPAR")

Return ONLY valid JSON in this exact format:
{{
  "entities": [
    {{"name": "Entity Name", "type": "hotel|city|brand", "mentions": 3}}
  ],
  "kpis": [
    {{"metric": "occupancy_pct", "value": 65.5, "unit": "%", "context": "Industry average"}}
  ],
  "benchmarks": [
    {{"metric": "RevPAR", "value": 7240, "segment": "Luxury", "region": "Mumbai"}}
  ],
  "insights": [
    {{"finding": "Weekend occupancy 15% higher than weekday", "impact": "high"}}
  ],
  "relationships": [
    {{"source": "Hotel A", "target": "Hotel B", "relation": "outperforms", "metric": "ADR"}}
  ]
}}

JSON:"""

    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Clean markdown code blocks if present
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        
        result_text = result_text.strip()
        
        knowledge_graph = json.loads(result_text)
        return knowledge_graph
    
    except json.JSONDecodeError as e:
        # Return empty structure if JSON parsing fails
        return {
            "entities": [],
            "kpis": [],
            "benchmarks": [],
            "insights": [],
            "relationships": [],
            "error": f"Failed to parse response: {str(e)}"
        }
    except Exception as e:
        return {
            "entities": [],
            "kpis": [],
            "benchmarks": [],
            "insights": [],
            "relationships": [],
            "error": str(e)
        }


def build_networkx_graph(knowledge_graph: Dict):
    """
    Build a NetworkX graph from extracted knowledge.
    
    Args:
        knowledge_graph: Dict from extract_knowledge_graph
        
    Returns:
        NetworkX graph object
    """
    import networkx as nx
    
    G = nx.Graph()
    
    # Add entity nodes
    for entity in knowledge_graph.get('entities', []):
        G.add_node(
            entity['name'],
            node_type=entity['type'],
            mentions=entity.get('mentions', 1)
        )
    
    # Add relationship edges
    for rel in knowledge_graph.get('relationships', []):
        G.add_edge(
            rel['source'],
            rel['target'],
            relation=rel['relation'],
            metric=rel.get('metric', '')
        )
    
    return G


def compare_with_database(benchmarks: List[Dict], db_metrics: Dict) -> List[Dict]:
    """
    Compare document benchmarks with live database metrics.
    
    Args:
        benchmarks: List of benchmark dicts from knowledge graph
        db_metrics: Dict of actual metrics from database
        
    Returns:
        List of comparison dicts
    """
    comparisons = []
    
    metric_map = {
        'occupancy': 'occupancy_pct',
        'occupancy_pct': 'occupancy_pct',
        'adr': 'adr',
        'revpar': 'revpar',
        'revenue': 'revenue',
        'realisation': 'realisation_pct',
        'cancellation': 'cancellation_pct'
    }
    
    for bench in benchmarks:
        metric_name = bench.get('metric', '').lower()
        
        # Map to our metric names
        mapped_metric = None
        for key, val in metric_map.items():
            if key in metric_name:
                mapped_metric = val
                break
        
        if not mapped_metric or mapped_metric not in db_metrics:
            continue
        
        db_value = db_metrics[mapped_metric]
        bench_value = bench.get('value', 0)
        
        if bench_value == 0:
            continue
        
        diff = db_value - bench_value
        diff_pct = (diff / bench_value) * 100
        
        comparisons.append({
            'metric': mapped_metric,
            'your_value': db_value,
            'benchmark': bench_value,
            'difference': diff,
            'difference_pct': diff_pct,
            'context': bench.get('context', bench.get('segment', 'Industry')),
            'status': 'above' if diff > 0 else 'below'
        })
    
    return comparisons