import markdown
import re
import os
import configparser
import shutil

def add_styling(html_content, config):
    """Add MathJax support with $ for inline and $$ for display math."""
    
    head = f"""
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config["content"]["title"]}</title>
    <link href="styles/monokai.css" rel="stylesheet">
    <link href="styles/opa.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.3.1/highlight.min.js"></script>
    <script>hljs.highlightAll();</script>
    <link rel="icon" href="icon.png">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
    """

    mathjax_head = """
    <script>
        window.MathJax = {
            tex: {
                inlineMath: [ ['$','$'] ],
                displayMath: [['$$', '$$']],
                processEscapes: true, 
                processEnvironments: true
            },
            options: {
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
            }
        };
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js"></script>
    """
    # Add title, icon and back to home link
    logo = f'<img src="icon.png" style="height: 50px; width: 50px; margin-right: 10px; border-radius: 50%;">'
    top_left = f"""
    <div class="top-left" style="position: fixed; left: 10px; display: flex; align-items: center;">
        {logo}    
        <h1>{config["content"]["title"]}</h1>
    </div>
    """

    # Add CSS to hide top-left elements on mobile
    style = f"""
    <style>
    @media only screen and (max-width: {config["style"]["mobile_width"]}px), 
        only screen and (max-device-width: {config["style"]["mobile_width"]}px) {{
        .top-left {{
            display: none !important;
        }}
    }}
    </style>
    """
    back_to_home_html = """
    <div style="position: fixed; top: 10px; right: 10px;">
    <a href="index.html" target="_blank"><i class="fas fa-home"></i></a>
    </div>
    """
    impressum_html = '<div style="position: fixed; bottom: 10px; left: 10px;"><a href="impressum.html">Impressum</a></div>'
    head += style + top_left + back_to_home_html + impressum_html

    html = f'<head>{head}{mathjax_head}</head>\n<div class="container">{html_content}</div>'
    
    return html

def remove_unwanted_hashes(text):
    # Initialize an empty list to store tags
    tags = []
    
    # Regular expression to match URLs
    url_pattern = re.compile(r'http\S+|www\.\S+')
    
    # Function to find tags outside of URLs
    def find_tags(match):
        url = match.group(0)
        # Find all tags in the URL
        url_tags = re.findall(r'#(\w+)', url)
        # Remove these tags from the main tags list
        for tag in url_tags:
            if tag in tags:
                tags.remove(tag)
        return url
    
    # Find all occurrences of #sometagname and store them in the tags list
    tags.extend(re.findall(r'#(\w+)', text))
    
    # Apply the function to exclude tags within URLs
    text = re.sub(url_pattern, find_tags, text)
    
    # Remove any #sometagname at the start of the string, separated by spaces
    text = re.sub(r'^(#\w+\s*)+', '', text)
    
    # Remove only the # if it appears elsewhere in the string
    text = re.sub(r'#(\w+)', r'\1', text)
    
    return text, tags

def remove_front_matter(text):
    # Remove front matter if it exists
    return re.sub(r'^---\n.*?---\n', '', text, flags=re.DOTALL)

def resolve_wiki_links(text):
    # Regular expression to match [[link|title]] or [[link]]
    pattern = r'\[\[(.*?)(?:\|(.*?))?\]\]'
    # Regular expression to match ![[link|title]] or ![[link]]
    pattern_exclam = r'!\[\[(.*?)(?:\|(.*?))?\]\]'
    
    # Function to replace the matched pattern with [title](link) or [link](link)
    def replace(match):
        link, title = match.groups()
        if not title:
            title = link
        return f'[{title}]({link})'
    
    # Function to replace the matched pattern with ![title](link) or ![link](link)
    def replace_exclam(match):
        link, title = match.groups()
        if not title:
            title = link
        else:
            if link.endswith(".png") or link.endswith(".jpg") or link.endswith(".webp") or link.endswith(".jpeg"):
                size = title
                return f'<img src="{link}" width="{size}">'
            
        return f'![{title}]({link})'
    
    # Use re.sub to replace all occurrences of the pattern
    transformed_text = re.sub(pattern_exclam, replace_exclam, text)
    transformed_text = re.sub(pattern, replace, transformed_text)
    
    return transformed_text

def replace_code_blocks(html):
    # Regular expression to match code blocks ```lang code ``` or ``` code ```
    pattern = r'```(\w+)?\n(.*?)```'
    
    def replace(match):
        lang = match.group(1) if match.group(1) else 'plaintext'
        code = match.group(2)
        return f'<pre><code class="language-{lang}">{code}</code></pre>'
    
    return re.sub(pattern, replace, html, flags=re.DOTALL)

def replace_md_tables(text):
    # Regular expression to match tables
    pattern = r'\n\|(.+)\|\n\|(?:\s*[-:]+\s*\|)+\n((?:\|.*\|\n)*)'
    
    def replace(match):
        header = match.group(1).split('|')
        header = [cell.strip() for cell in header if cell.strip()]
        
        body = match.group(2).strip().split('\n')
        body_rows = []
        for row in body:
            cells = row.split('|')
            cells = [cell.strip() for cell in cells if cell.strip()]
            body_rows.append(''.join(f'<td>{cell}</td>' for cell in cells))
        
        header_html = ''.join(f'<th>{cell}</th>' for cell in header)
        body_html = ''.join(f'<tr>{row}</tr>' for row in body_rows)
        
        return f'<table class="table-bordered"><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>'
    
    return re.sub(pattern, replace, text)

def read_config(config_path):
    config = configparser.ConfigParser()
    if config_path is not None:
        config.read(config_path)
    else:
        config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
    
    return config

def generate_opa_css(config):
    css_head = f"""
    body {{
        margin: 0;
        padding: 20px;
        min-height: 100vh;
        line-height: 1.6;
        font-family: Consolas, "Liberation Mono", Monaco, "Courier New", monospace;
        background-color: {config["style"]["dark_bg"]}; /* Dark bg */
        color: {config["style"]["text"]}; /* Text color */
        display: flex;
        justify-content: center;
    }}
    .container {{
        max-width: 800px;
        width: 100%;
        padding: 40px;
        border-radius: 8px;
    }}
    a {{
        color: {config["style"]["link"]}; /* Link color */
        text-decoration: none;
    }}
    a:hover {{
        color: {config["style"]["link_hover"]}; /* Link hover color */
        text-decoration: underline;
    }}
    h1 {{
        margin: 0.2em 0 0.1em 0;
    }}
    h2, h3, h4, h5, h6 {{
        color: #f0e3c0;
        margin: 0.01em 0 0.03em 0;  /* Very compact spacing */
        font-family: Consolas, monospace;
        letter-spacing: 0.5px;
    }}
    ul {{
        padding-left: 20px;
        margin-top: 0.05em;    /* Added to reduce space after headings when followed by lists */
        margin-bottom: 0.5em;
    }}
    p {{
        margin-top: 0.05em;
    }}
    li {{
        margin-bottom: 0.5em;
    }}
    pre, code {{
        font-family: Consolas, monospace;
        background-color: {config["style"]["code_bg"]}; /* code bg */
        overflow-x: auto;
        font-size: 14px;
        line-height: 1.4;
    }}
    
    b, strong {{
        color: {config["style"]["bold"]}; /* Color for bold text */
    }}
    i, em {{
        color: {config["style"]["italic"]}; /* Color for italic text */
    }}
    .table-bordered {{
        empty-cells: show;
        border-collapse: collapse;
        width: 75%;
    }}
    .table-bordered th, .table-bordered td {{
        border: 2px solid rgba(255, 255, 255, 0.2);
    }}
    .page-list {{
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin-top: 1rem;
    }}
    .page-card {{
        background-color: rgba(40, 40, 40, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        padding: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .page-card:hover {{
        background-color: rgba(50, 50, 50, 0.8);
    }}
    .page-info {{
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }}
    .date {{
        font-size: 0.9em;
        color: #888;
    }}
    .tags {{
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
    }}
    .tag {{
        background-color: {config["style"]["tag_bg"]};
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.8em;
    }}

    input {{
        padding: 10px;                      /* Space inside the input field */
        width: 100%;                        /* Full width */
        max-width: 400px;                  /* Maximum width */
        border: {config["style"]["search_border_size"]}px solid {config["style"]["search_border"]};            /* Border style */
        border-radius: 4px;                /* Rounded corners */
        font-size: 12px;                   /* Font size */
        background-color: {config["style"]["search_bg"]};        /* Change background color */
        transition: border-color 0.3s;     /* Smooth transition for border color */
        color: {config["style"]["search_text"]}; /* Text color */
    }}

    input:focus {{
        outline: none;                      /* Remove default outline */
        border-color: {config["style"]["search_border_focus"]};             /* Change border color on focus */
    }}

    /* Base admonition styling */
    .admonition {{
        border-left: 4px solid #bbb;
        padding: 10px 15px;
        margin: 10px 0;
        border-radius: 6px;
        background-color: #2e2e2e;
        color: #e0e0e0;
        font-family: "Consolas", monospace;
    }}

    /* Warning admonition styling */
    .admonition.warning {{
        border-left-color: #ff6b6b;
        background-color: #402c2c;
        color: #ffeaea;
    }}

    .admonition.warning .admonition-title {{
        color: #ff9b9b;
    }}

    /* Question admonition styling */
    .admonition.question {{
        border-left-color: #6baaff;
        background-color: #2c3b40;
        color: #d2e8ff;
    }}

    .admonition.question .admonition-title {{
        color: #a3d7ff;
    }}

    /* Callout admonition styling */
    .admonition.callout {{
        border-left-color: #ffcc6b;
        background-color: #40392c;
        color: #ffe8d2;
    }}

    .admonition.callout .admonition-title {{
        color: #ffd3a3;
    }}

    /* Quote admonition styling */
    .admonition.quote {{
        border-left-color: #a6a6a6;
        background-color: #3b3b3b;
        color: #d6d6d6;
        font-style: italic;
    }}

    .admonition.quote .admonition-title {{
        color: #c6c6c6;
    }}

    /* Title styling */
    .admonition-title {{
        font-size: 1em; /* Slightly smaller title */
        margin-bottom: 5px;
        letter-spacing: 0.05em;
        font-weight: bold;
    }}

    .admonition p {{
        margin: 0;
        line-height: 1.5;
    }}
    """
    with open(os.path.join(os.path.dirname(__file__), "styles", "opa.css"), "w") as css_file:
        css_file.write(css_head)

def replace_callouts(text):
    # Regular expression to match the callout pattern, including multiline content
    pattern = r'> \[!(\w+)\] (.+)\n((?:> .*\n)*)'
    
    def repl(match):
        callout_type = match.group(1)
        title = match.group(2)
        content = match.group(3).replace('> ', '').replace('\n', '\n    ')
        return f'!!! {callout_type} "{title}"\n    {content}'
    
    # Replace the callouts using the regular expression
    return re.sub(pattern, repl, text)

def md_to_html(path, output_path=None, config_path=None):
    with open(path, "r", encoding="utf-8") as input_file:
        text = input_file.read()

    # Read config file
    config = read_config(config_path)

    # Generate style sheet opa.css
    generate_opa_css(config)
    copy_style_files(output_path)
         
    # Md processing
    text, tags = remove_unwanted_hashes(text)
    text = remove_front_matter(text)
    text = resolve_wiki_links(text)
    text = replace_code_blocks(text)
    text = replace_md_tables(text)
    text = replace_callouts(text)

    # html processing
    html = markdown.markdown(text, extensions=["admonition"])
    html = add_styling(html, config)

    md_file_name = path.split(os.sep)[-1]
    if output_path is not None:
        output = f"{output_path}{os.sep}{md_file_name.split('.')[0]}.html"
        # save html file
        with open(output, "w", encoding="utf-8", errors="xmlcharrefreplace") as output_file:
            output_file.write(html)
        
        return f"{md_file_name.split('.')[0]}.html", tags

    output = f"{path.split(".")[0]}.html"
    # save html file
    with open(output, "w", encoding="utf-8", errors="xmlcharrefreplace") as output_file:
        output_file.write(html)
        
    return f"{md_file_name.split('.')[0]}.html", tags


def copy_style_files(output_path):
    # Define the source directory containing the style files
    source_dir = os.path.join(os.path.dirname(__file__), "styles")
    
    # Define the destination directory in the output path
    dest_dir = os.path.join(output_path, "styles")
    
    # Create the destination directory if it doesn't exist
    os.makedirs(dest_dir, exist_ok=True)
    
    # Copy each file from the source directory to the destination directory
    for file_name in os.listdir(source_dir):
        full_file_name = os.path.join(source_dir, file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, dest_dir)

def generate_home_page(pages: list, output_path, config_path=None):
    # config file
    config = read_config(config_path)
    generate_opa_css(config)
    copy_style_files(output_path)
    
    # Define the home page content
    home_page_content = f"""
    <h1>{config["content"]["home_title"]}</h1>
    <p>{config["content"]["welcome_text"]}</p>
    <div class="page-list">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <input type="text" id="search-bar" placeholder="Search by title, tag or date..." onkeyup="filterPages()">
        <div class="social-icons">
            <a href="{config['content']['ko_fi']}" target="_blank"><i class="fas fa-coffee"></i></a>
            <a href="{config['content']['soundcloud']}" target="_blank"><i class="fab fa-soundcloud"></i></a>
            <a href="{config['content']['instagram']}" target="_blank"><i class="fab fa-instagram"></i></a>
            <a href="{config['content']['youtube']}" target="_blank"><i class="fab fa-youtube"></i></a>
            <a href="{config['content']['linkedin']}" target="_blank"><i class="fab fa-linkedin"></i></a>
            <a href="{config['content']['discord']}" target="_blank"><i class="fab fa-discord"></i></a>
            <a href="{config['content']['github']}" target="_blank"><i class="fab fa-github"></i></a>
            <a href="mailto:{config['content']['email']}"><i class="fas fa-envelope"></i></a>
        </div>
    </div>
    """

    # Add page cards to the home page content
    for page in pages:
        # Generate tags HTML if page has tags
        tags_html = ""
        if "tags" in page:
            tags_html = "".join([f'<span class="tag">{tag}</span>' for tag in page["tags"]])
        
        # Generate the page card
        home_page_content += f"""
        <div class="page-card">
            <div class="page-info">
                <a href="{page["name"]}">{page["name"].replace('.html', '')}</a>
                <span class="date">{page["date"]}</span>
            </div>
            <div class="tags">
                {tags_html}
            </div>
        </div>
        """
    
    home_page_content += "</div>"

    home_page_content += """
    <script>
        document.addEventListener('DOMContentLoaded', function() {
        let cards = document.getElementsByClassName('page-card');
        
        for (let card of cards) {
            let tags = card.querySelector('div.tags').textContent.toLowerCase();
            
            if (tags.includes('hidden')) {
                card.style.display = "none";
            }
        }
        });
        function filterPages() {
            let input = document.getElementById('search-bar').value.toLowerCase();
            let cards = document.getElementsByClassName('page-card');
            
            for (let card of cards) {
                let title = card.querySelector('a').textContent.toLowerCase();
                let tags = card.querySelector('div.tags').textContent.toLowerCase();
                let date = card.querySelector('span.date').textContent.toLowerCase();
                
                if (tags.includes('hidden')) {
                    card.style.display = "none";
                } else if (title.includes(input) || tags.includes(input) || date.includes(input)) {
                    card.style.display = "";
                } else {
                    card.style.display = "none";
                }
            }
        }
    </script>
    <style>
        .social-icons a {
            margin-left: 10px;
            color: #000;
            text-decoration: none;
        }
        .social-icons a:hover {
            color: #007bff;
        }
    </style>
    """
    # Add styling to the home page content
    home_page = add_styling(home_page_content, config)

    # save home page
    with open(f"{output_path}{os.sep}index.html", "w", encoding="utf-8", errors="xmlcharrefreplace") as output_file:
        output_file.write(home_page)
    
    # generate impressum
    generate_impressum(output_path, config_path)

def generate_impressum(output_path, config_path=None):
    # Read the config file
    config = read_config(config_path)
    
    impressum = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Impressum</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
            }}
            h1 {{
                font-size: 24px;
            }}
            p {{
                margin: 10px 0;
            }}
        </style>
    </head>
    <body>
        <h1>Impressum</h1>
        <p><strong>Name:</strong>{config["content"]["name"]}</p>
        <p><strong>Address:</strong> {config["content"]["address"]}</p>
        <p><strong>Email:</strong> {config["content"]["email"]}</p>
        <h2>Disclaimer</h2>
        <p>All information on this website is provided for general information purposes only. I do not take responsibility for the accuracy, completeness, or timeliness of the information provided.</p>
        <p>Despite careful control, I assume no liability for the content of external links. The operators of the linked pages are solely responsible for their content.</p>
    </body>
    </html>
    """

    # Add styling to the impressum content
    impressum = add_styling(impressum, config)

    # Save the impressum file
    with open(f"{output_path}{os.sep}impressum.html", "w", encoding="utf-8", errors="xmlcharrefreplace") as output_file:
        output_file.write(impressum)
