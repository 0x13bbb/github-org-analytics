import os
import markdown
import json
import pandas as pd
import argparse

def markdown_to_html(content):
    processed_content = content.replace('\n', '  \n')
    return markdown.markdown(processed_content)

def json_to_html_table(json_data):
    data = json.loads(json_data)

    if isinstance(data, dict):
        data = [data]

    df = pd.DataFrame(data)
    df['AICommitSummary'] = df['AICommitSummary'].str.replace('\n', '<br/>')


    html_table = df.to_html(index=False, escape=False)
    
    return '<div class="table-container">' + html_table + '</div>'

def process_directory(directory):
    sections = {
        'markdown': [],
        'images': [],
        'html': [],
        'json': []
    }
    
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        
        if filename.endswith('.md'):
            with open(filepath, 'r') as f:
                sections['markdown'].append(markdown_to_html(f.read()))
        elif filename.endswith(('.jpg', '.png', '.gif')):
            sections['images'].append(f'<img src="{filepath}" alt="{filename}" width="800">')
        elif filename.endswith('.html'):
            with open(filepath, 'r') as f:
                sections['html'].append(f.read())
        elif filename.endswith('.json'):
            if "commit_stats" in filename:
                continue

            with open(filepath, 'r') as f:
                sections['json'].append(json_to_html_table(f.read()))

    css_styles = """
<style>
    table {
    border-collapse: separate;
    border-spacing: 0;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 0 0 1px #ddd;
    }
    th, td {
        padding: 12px 15px;
        text-align: left;
        border-right: 1px solid #ddd;
        border-bottom: 1px solid #ddd;
    }
    thead th {
        background-color: #fff2d9;
        border-top: 1px solid #ddd;
    }
    th:first-child, td:first-child {
        border-left: 1px solid #ddd;
    }
    tr:last-child td {
        border-bottom: none;
    }
    tr:hover {
        background-color: #fff2d9;
    }
    th:last-child, td:last-child {
        border-right: none;
    }
    thead th:first-child {
        border-top-left-radius: 8px;
    }
    thead th:last-child {
        border-top-right-radius: 8px;
    }
    tbody tr:last-child td:first-child {
        border-bottom-left-radius: 8px;
    }
    tbody tr:last-child td:last-child {
        border-bottom-right-radius: 8px;
    }
    .table-container {
      width: 100%;
      overflow-x: auto;
      margin-top: 20px;
    }

    .dataframe {
      margin: 0 auto;
      min-width: 100%;
      width: 1600px;
    }
</style>
"""
    
    combined_html = f'''
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>"celestiaorg" analytics</title>
    {css_styles}
</head>
<body style="background-color: #fffaf0;font-family: Quicksand, sans-serif;"><div style="max-width: 1000px; margin: 0 auto; padding: 80px 20px;">'''

    combined_html += '<h1 style="text-align: center;">"celestiaorg" Github Analytics</h1>'
    for section, content in sections.items():
        if content:
            if section == 'markdown':
                combined_html += f'<h2 style="margin-top: 40px">🤖 AI summary</h2>'
            elif section == 'images':
                combined_html += f'<h2 style="margin-top: 40px">📈 Charts</h2>'
            elif section == 'html':
                combined_html += f'<h2 style="margin-top: 40px">🧑‍🤝‍🧑 Public organization members</h2>'
            elif section == 'json':
                combined_html += f'<h2 style="margin-top: 40px">🗂️ Tables</h2>'

            combined_html += ''.join(content)
    combined_html += '</div></body></html>'
    
    return combined_html


def main():
    parser = argparse.ArgumentParser(description="Generate a report from a specified directory.")
    parser.add_argument("directory", help="Path to the directory to process")
    parser.add_argument("-o", "--output", default="output.html", help="Output file name (default: output.html)")

    args = parser.parse_args()

    result = process_directory(args.directory)

    with open(args.output, 'w') as f:
        f.write(result)

    print(f"Report generated and saved to {args.output}")

if __name__ == "__main__":
    main()