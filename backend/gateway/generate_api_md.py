import os
import sys
from fastapi.routing import APIRoute, APIWebSocketRoute

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(".."))

from app.main import app

def generate_markdown():
    lines = ["# PIHUB Backend API Reference\n", "This document lists all the API endpoints available in the backend.\n"]
    
    categories = {}
    
    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            methods = ", ".join(route.methods - {"OPTIONS"})
            name = route.name.replace("_", " ").title()
            
            # extract first tag or use path prefix as category
            category = "General"
            if route.tags:
                category = route.tags[0].title()
            else:
                parts = [p for p in path.split("/") if p]
                if parts:
                    category = parts[0].title()
                    
            if category not in categories:
                categories[category] = []
                
            categories[category].append(f"- **{methods}** `{path}` - {name}")
            
        elif isinstance(route, APIWebSocketRoute):
            path = route.path
            name = route.name.replace("_", " ").title()
            category = "Websocket"
            if category not in categories:
                categories[category] = []
            categories[category].append(f"- **WS** `{path}` - {name}")
            
    for cat, routes in sorted(categories.items()):
        lines.append(f"\n## {cat}\n")
        for r in routes:
            lines.append(r)
            
    with open("../docs/api/api_reference.md", "w") as f:
        f.write("\n".join(lines))
        
if __name__ == "__main__":
    generate_markdown()
    print("Done")
