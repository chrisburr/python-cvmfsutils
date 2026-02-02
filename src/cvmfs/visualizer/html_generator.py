# -*- coding: utf-8 -*-
"""
HTML generator for CVMFS catalog visualization.

Generates a self-contained HTML file with an interactive D3.js sunburst chart.
"""

import json
from typing import Union

from .tree_builder import CatalogNode

# D3.js CDN URL
D3_CDN = "https://d3js.org/d3.v7.min.js"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CVMFS Catalog Visualizer - {repo_name}</title>
    <script src="{d3_cdn}"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        header {{
            background: #16213e;
            padding: 1rem 2rem;
            border-bottom: 1px solid #0f3460;
        }}

        header h1 {{
            font-size: 1.5rem;
            font-weight: 500;
        }}

        header .repo-name {{
            color: #e94560;
            font-family: monospace;
        }}

        .container {{
            display: flex;
            flex: 1;
            overflow: hidden;
        }}

        .chart-container {{
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 1rem;
        }}

        .sidebar {{
            width: 350px;
            background: #16213e;
            padding: 1.5rem;
            overflow-y: auto;
            border-left: 1px solid #0f3460;
        }}

        .sidebar h2 {{
            font-size: 1rem;
            font-weight: 500;
            margin-bottom: 1rem;
            color: #e94560;
        }}

        .info-panel {{
            background: #1a1a2e;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }}

        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #0f3460;
        }}

        .info-row:last-child {{
            border-bottom: none;
        }}

        .info-label {{
            color: #888;
            font-size: 0.85rem;
        }}

        .info-value {{
            font-family: monospace;
            font-size: 0.9rem;
        }}

        .info-value.path {{
            word-break: break-all;
            text-align: right;
            max-width: 200px;
        }}

        .legend {{
            margin-top: 1rem;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 0.5rem;
            font-size: 0.85rem;
        }}

        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
            margin-right: 0.75rem;
        }}

        .large-indicator {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background: #e94560;
            border-radius: 4px;
            font-size: 0.75rem;
            margin-top: 0.5rem;
        }}

        .stats {{
            font-size: 0.8rem;
            color: #888;
            margin-top: 1rem;
        }}

        .breadcrumb {{
            font-family: monospace;
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 1rem;
            word-break: break-all;
        }}

        .breadcrumb span {{
            color: #e94560;
        }}

        .instructions {{
            font-size: 0.8rem;
            color: #666;
            margin-top: 1rem;
            line-height: 1.5;
        }}

        svg text {{
            pointer-events: none;
            user-select: none;
        }}
    </style>
</head>
<body>
    <header>
        <h1>CVMFS Catalog Visualizer - <span class="repo-name">{repo_name}</span></h1>
    </header>

    <div class="container">
        <div class="chart-container">
            <svg id="chart"></svg>
        </div>

        <div class="sidebar">
            <div class="breadcrumb">
                Current view: <span id="breadcrumb">/</span>
            </div>

            <h2>Selected Catalog</h2>
            <div class="info-panel" id="info-panel">
                <div class="info-row">
                    <span class="info-label">Path</span>
                    <span class="info-value path" id="info-path">/</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Catalog Size</span>
                    <span class="info-value" id="info-size">-</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Cumulative Cost</span>
                    <span class="info-value" id="info-cost">-</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Depth</span>
                    <span class="info-value" id="info-depth">-</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Hash</span>
                    <span class="info-value" id="info-hash" style="font-size: 0.75rem;">-</span>
                </div>
                <div id="large-badge"></div>
            </div>

            <h2>Size Legend</h2>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color" style="background: #22c55e;"></div>
                    <span>&lt; 2 MB (Small)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #eab308;"></div>
                    <span>2 - 10 MB (Medium)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #f97316;"></div>
                    <span>10 - 50 MB (Large)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ef4444;"></div>
                    <span>&gt; 50 MB (Very Large)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: repeating-linear-gradient(45deg, #ef4444, #ef4444 2px, #1a1a2e 2px, #1a1a2e 4px);"></div>
                    <span>Exploration stopped</span>
                </div>
            </div>

            <div class="instructions">
                <strong>Instructions:</strong><br>
                • Click on a segment to zoom in<br>
                • Click center to zoom out<br>
                • Hover for details
            </div>

            <div class="stats">
                <strong>Build Statistics:</strong><br>
                Catalogs downloaded: {catalogs_downloaded}<br>
                Total downloaded: {total_downloaded}
            </div>
        </div>
    </div>

    <script>
    const data = {data_json};

    const width = 700;
    const height = 700;
    const radius = width / 6;

    // Color scale based on size
    function getColor(d) {{
        const size = d.data.size || 0;
        const mb = size / (1024 * 1024);

        if (mb < 2) return "#22c55e";      // Green - small
        if (mb < 10) return "#eab308";     // Yellow - medium
        if (mb < 50) return "#f97316";     // Orange - large
        return "#ef4444";                   // Red - very large
    }}

    // Format bytes
    function formatBytes(bytes) {{
        if (bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }}

    // Create hierarchy
    const root = d3.hierarchy(data)
        .sum(d => d.children && d.children.length ? 0 : Math.max(d.size, 1))
        .sort((a, b) => b.value - a.value);

    const partition = d3.partition()
        .size([2 * Math.PI, root.height + 1]);

    partition(root);

    root.each(d => d.current = d);

    // Create SVG
    const svg = d3.select("#chart")
        .attr("viewBox", [-width / 2, -height / 2, width, height])
        .style("font", "10px sans-serif");

    // Arc generator
    const arc = d3.arc()
        .startAngle(d => d.x0)
        .endAngle(d => d.x1)
        .padAngle(d => Math.min((d.x1 - d.x0) / 2, 0.005))
        .padRadius(radius * 1.5)
        .innerRadius(d => d.y0 * radius)
        .outerRadius(d => Math.max(d.y0 * radius, d.y1 * radius - 1));

    // Create paths
    const path = svg.append("g")
        .selectAll("path")
        .data(root.descendants().slice(1))
        .join("path")
        .attr("fill", d => getColor(d))
        .attr("fill-opacity", d => arcVisible(d.current) ? (d.children ? 0.8 : 0.6) : 0)
        .attr("stroke", d => {{
            if (d.data.is_large && d.children && d.children.length === 0) {{
                return "#1a1a2e";
            }}
            return "none";
        }})
        .attr("stroke-width", d => {{
            if (d.data.is_large && d.children && d.children.length === 0) {{
                return 2;
            }}
            return 0;
        }})
        .attr("stroke-dasharray", d => {{
            if (d.data.is_large && d.children && d.children.length === 0) {{
                return "4,2";
            }}
            return "none";
        }})
        .attr("pointer-events", d => arcVisible(d.current) ? "auto" : "none")
        .attr("d", d => arc(d.current))
        .style("cursor", "pointer")
        .on("mouseover", handleMouseOver)
        .on("mouseout", handleMouseOut)
        .on("click", clicked);

    // Center circle for zooming out
    const parent = svg.append("circle")
        .datum(root)
        .attr("r", radius)
        .attr("fill", "#16213e")
        .attr("pointer-events", "all")
        .style("cursor", "pointer")
        .on("click", clicked)
        .on("mouseover", handleMouseOver)
        .on("mouseout", handleMouseOut);

    // Center text
    const centerText = svg.append("text")
        .attr("text-anchor", "middle")
        .attr("fill", "#eee")
        .attr("dy", "0.35em")
        .style("font-size", "14px")
        .text("Click to zoom out");

    // Update info panel
    function updateInfo(d) {{
        document.getElementById("info-path").textContent = d.data.path || "/";
        document.getElementById("info-size").textContent = formatBytes(d.data.size || 0);
        document.getElementById("info-cost").textContent = formatBytes(d.data.cumulative_cost || 0);
        document.getElementById("info-depth").textContent = d.data.depth || 0;
        document.getElementById("info-hash").textContent = d.data.hash || "-";

        const badge = document.getElementById("large-badge");
        if (d.data.is_large) {{
            badge.innerHTML = '<span class="large-indicator">Large catalog - exploration stopped</span>';
        }} else {{
            badge.innerHTML = "";
        }}
    }}

    function handleMouseOver(event, d) {{
        updateInfo(d);
        d3.select(this).attr("fill-opacity", 1);
    }}

    function handleMouseOut(event, d) {{
        d3.select(this).attr("fill-opacity", d => arcVisible(d.current) ? (d.children ? 0.8 : 0.6) : 0);
    }}

    // Initial info
    updateInfo(root);

    function clicked(event, p) {{
        parent.datum(p.parent || root);

        root.each(d => d.target = {{
            x0: Math.max(0, Math.min(1, (d.x0 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
            x1: Math.max(0, Math.min(1, (d.x1 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
            y0: Math.max(0, d.y0 - p.depth),
            y1: Math.max(0, d.y1 - p.depth)
        }});

        const t = svg.transition().duration(750);

        path.transition(t)
            .tween("data", d => {{
                const i = d3.interpolate(d.current, d.target);
                return t => d.current = i(t);
            }})
            .filter(function(d) {{
                return +this.getAttribute("fill-opacity") || arcVisible(d.target);
            }})
            .attr("fill-opacity", d => arcVisible(d.target) ? (d.children ? 0.8 : 0.6) : 0)
            .attr("pointer-events", d => arcVisible(d.target) ? "auto" : "none")
            .attrTween("d", d => () => arc(d.current));

        // Update breadcrumb
        let breadcrumb = p.data.path || "/";
        document.getElementById("breadcrumb").textContent = breadcrumb;

        updateInfo(p);
    }}

    function arcVisible(d) {{
        return d.y1 <= 3 && d.y0 >= 1 && d.x1 > d.x0;
    }}
    </script>
</body>
</html>
"""


def _format_bytes(bytes_val: int) -> str:
    """Format bytes as human-readable string."""
    if bytes_val == 0:
        return "0 B"
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while bytes_val >= 1024 and i < len(suffixes) - 1:
        bytes_val /= 1024
        i += 1
    return f"{bytes_val:.2f} {suffixes[i]}"


def generate_html(
    root_node: CatalogNode,
    repo_name: str,
    catalogs_downloaded: int = 0,
    total_downloaded: int = 0,
) -> str:
    """Generate a self-contained HTML visualization.

    Args:
        root_node: Root CatalogNode from tree builder
        repo_name: Repository name for display
        catalogs_downloaded: Number of catalogs downloaded
        total_downloaded: Total bytes downloaded

    Returns:
        Complete HTML string
    """
    data_dict = root_node.to_dict()
    data_json = json.dumps(data_dict, indent=2)

    return HTML_TEMPLATE.format(
        repo_name=repo_name,
        d3_cdn=D3_CDN,
        data_json=data_json,
        catalogs_downloaded=catalogs_downloaded,
        total_downloaded=_format_bytes(total_downloaded),
    )
