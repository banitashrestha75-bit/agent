import os
import re
from groq import Groq
from e2b_code_interpreter import Sandbox

# Profiling script to run inside the E2B sandbox to understand the file structure
PROFILING_SCRIPT_TEMPLATE = """
import os
import pandas as pd
import json

file_path = "{file_path}"
ext = os.path.splitext(file_path)[1].lower()
print(f"File: {{os.path.basename(file_path)}}")
print(f"Size: {{os.path.getsize(file_path)}} bytes")

if ext == '.csv':
    try:
        df = pd.read_csv(file_path)
        print("Type: CSV")
        print(f"Rows: {{df.shape[0]}}, Columns: {{df.shape[1]}}")
        print("Columns and types:")
        print(df.dtypes.to_string())
        print("\\nFirst 3 rows:")
        print(df.head(3).to_string())
    except Exception as e:
        print(f"Error reading CSV: {{e}}")
elif ext == '.json':
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("Type: JSON")
        if isinstance(data, list):
            print(f"JSON contains a list of {{len(data)}} items.")
            if len(data) > 0:
                print("First item preview:")
                print(json.dumps(data[0], indent=2)[:1000])
        elif isinstance(data, dict):
            print("JSON contains a dictionary.")
            print("Top-level keys:", list(data.keys()))
            print("Data preview:")
            print(json.dumps(data, indent=2)[:1000])
    except Exception as e:
        print(f"Error reading JSON: {{e}}")
elif ext in ['.txt', '.md']:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(2000)
        print("Type: Text/Markdown")
        print("Content Preview (First 2000 chars):")
        print(content)
    except Exception as e:
        print(f"Error reading Text file: {{e}}")
elif ext == '.pdf':
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        print("Type: PDF")
        print(f"Total Pages: {{len(reader.pages)}}")
        text = ""
        if len(reader.pages) > 0:
            text = reader.pages[0].extract_text() or ""
        print("Content Preview (Page 1 first 2000 chars):")
        print(text[:2000])
    except Exception as e:
        print(f"Error reading PDF: {{e}}")
else:
    print("Unknown file type, showing first 500 bytes:")
    try:
        with open(file_path, 'rb') as f:
            print(f.read(500))
    except Exception as e:
        print(e)
"""

def extract_code_block(text):
    """
    Helper to extract the python code block from model response.
    """
    pattern = r"```python(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def profile_file(sandbox, file_path_in_sandbox):
    """
    Runs the profiling script inside the E2B sandbox to extract metadata.
    """
    # First, make sure pypdf is installed in case we need to profile a PDF
    try:
        sandbox.commands.run("pip install pypdf")
    except Exception as e:
        print(f"Warning: could not run pip install pypdf in sandbox: {e}")
        
    script = PROFILING_SCRIPT_TEMPLATE.format(file_path=file_path_in_sandbox)
    execution = sandbox.run_code(script)
    if execution.error:
        return f"Error profiling file: {execution.error.name}\n{execution.error.value}"
    return execution.text

def generate_analysis_code(groq_client, model_name, user_query, file_name, file_profile, chat_history=[]):
    """
    Phase 1: Ask the Groq LLM to write the python analysis code based on the file profile and query.
    """
    system_prompt = f"""You are an advanced AI Data Analyst and Python coding agent.
Your job is to generate Python code to answer the user's query about the uploaded document.

Document Details:
Filename: {file_name}
File Profiling Summary (from the sandbox environment):
{file_profile}

Instructions:
1. Think carefully about the user's query and formulate a plan.
2. Generate a single, self-contained Python code block inside a ```python ... ``` markdown block.
3. The code will execute in an isolated E2B sandbox. The document is stored at the path: '{file_name}'.
4. In your Python code:
   - Load the file '{file_name}' using standard Python libraries (pandas for CSV, pypdf for PDF, json for JSON, open for txt/md).
   - Perform any necessary data processing, calculations, or analysis.
   - Print the results clearly to standard output.
   - If the user wants a chart, plot, or visualization, use matplotlib or seaborn and ALWAYS call `plt.show()` at the end of the plotting code. Do not attempt to save the image to disk. The E2B sandbox will capture `plt.show()` automatically and return it to us.
5. Provide a brief explanation of what your code intends to do under the header '### Plan'.

Format your response exactly as follows:
### Plan
(Your plan here)

### Code
```python
# your code here
```
"""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add chat history for context if any
    for h in chat_history[-6:]:  # Limit history size
        messages.append({"role": h["role"], "content": h["content"]})
        
    messages.append({"role": "user", "content": f"Query: {user_query}"})

    response = groq_client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0.1
    )
    
    content = response.choices[0].message.content
    plan_match = re.search(r"### Plan(.*?)(### Code|```python)", content, re.DOTALL)
    plan = plan_match.group(1).strip() if plan_match else "Formulating analysis..."
    code = extract_code_block(content)
    
    return plan, code

def execute_sandbox_code(sandbox, code):
    """
    Runs the Python code inside the E2B sandbox and returns outputs.
    """
    execution = sandbox.run_code(code)
    
    stdout = execution.text or ""
    stderr = ""
    if execution.error:
        stderr = f"{execution.error.name}: {execution.error.value}\n{execution.error.traceback}"
        
    # Extract base64 PNGs from the results list
    charts = []
    if execution.results:
        for result in execution.results:
            if result.png:
                charts.append(result.png)
                
    return stdout, stderr, charts

def generate_final_summary(groq_client, model_name, user_query, file_name, file_profile, code_run, execution_output, chat_history=[]):
    """
    Phase 2: Feed the execution output back to the LLM to write a final human-readable summary.
    """
    system_prompt = f"""You are an advanced AI Data Analyst.
You have just run Python code inside an E2B Sandbox to answer a user's query about an uploaded document.

Document Name: {file_name}
File Profile:
{file_profile}

Code Executed:
```python
{code_run}
```

Console Output from Execution:
```text
{execution_output}
```

Write a clear, professional, and comprehensive final explanation/summary of the results that directly answers the user's query.
- Focus on explaining the insights, calculations, and data patterns discovered in the execution output.
- Reference the charts if any were generated.
- If the code encountered errors or didn't output what was expected, explain what went wrong and suggest how the user can refine their query.
"""

    messages = [{"role": "system", "content": system_prompt}]
    for h in chat_history[-6:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": f"Query: {user_query}"})

    response = groq_client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0.3
    )
    
    return response.choices[0].message.content
