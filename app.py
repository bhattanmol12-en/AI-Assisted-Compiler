import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk
import re
import subprocess
import os
import tempfile
import sys

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ==============================
# TOKEN DEFINITIONS
# ==============================

TOKENS = [
    ('KEYWORD', r'\b(int|float|if|else|elif|for|while|return|printf|main|public|class|static|void|String|System\.out\.print(ln)?|def|import|from|namespace|using|cout|cin|endl|std)\b'),
    ('IDENTIFIER', r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'),
    ('NUMBER', r'\b\d+(\.\d+)?\b'),
    ('STRING', r'"[^"]*"'),
    ('OPERATOR', r'[+\-*/=<>]'),
    ('SEMICOLON', r';'),
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('LBRACE', r'\{'),
    ('RBRACE', r'\}')
]

declared_variables = set()

# Theme Colors
THEME = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "cursor": "#ffffff",
    "select_bg": "#264f78",
    "keyword": "#569cd6",    # Blue
    "identifier": "#9cdcfe", # Light blue
    "number": "#b5cea8",     # Light green
    "string": "#ce9178",     # Orange/Brown
    "operator": "#d4d4d4",   # Default
    "comment": "#6a9955",    # Green
    "line_fg": "#858585",
    "line_bg": "#1e1e1e",
    "button_bg": "#0e639c",
    "button_fg": "#ffffff",
    "panel_bg": "#252526"
}

# ==============================
# LEXICAL ANALYZER
# ==============================

def tokenize(code):
    tokens = []
    token_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKENS)
    for match in re.finditer(token_regex, code):
        for name, _ in TOKENS:
            if match.group(name):
                tokens.append((name, match.group(name)))
                break
    return tokens

# ==============================
# SYNTAX CHECKER
# ==============================

def check_syntax(code, lang):
    errors = []
    lines = code.split("\n")
    brace_stack = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        
        # Python uses # for comments, C-family uses //
        if lang == "Python" and stripped.startswith("#"):
            continue
        elif lang != "Python" and stripped.startswith("//"):
            continue
            
        # C/C++/Java check semicolons 
        if lang in ["C", "C++", "Java"]:
            if (
                not stripped.endswith(";")
                and not stripped.endswith("{")
                and not stripped.endswith("}")
                and not stripped.startswith("if")
                and not stripped.startswith("else")
                and not stripped.startswith("for")
                and not stripped.startswith("while")
                and not stripped.startswith("main")
                and not stripped.startswith("public")
                and not stripped.startswith("class")
                and not stripped.startswith("static")
                and not stripped.startswith("//")
                and not stripped.startswith("#")
                and not stripped.startswith("using")
            ):
                errors.append(f"Line {i+1}: Missing semicolon")

        # Brace matching applies to non-Python languages
        if lang != "Python":
            for char in stripped:
                if char == "{":
                    brace_stack.append("{")
                elif char == "}":
                    if brace_stack:
                        brace_stack.pop()
                    else:
                        errors.append(f"Line {i+1}: Unmatched closing brace")

    if lang != "Python" and brace_stack:
        errors.append("Unmatched opening brace at end of file")

    return errors

# ==============================
# SEMANTIC CHECKER
# ==============================

def semantic_analysis(code, lang):
    if lang == "Python":
        return [] # Dynamic typing, skip strict semantic checks for Python
        
    errors = []
    declared_variables.clear()
    lines = code.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue

        # Variable declaration
        match = re.match(r'(int|float|String|double|char)\s+([a-zA-Z_][a-zA-Z0-9_]*)', stripped)
        if match:
            var_name = match.group(2)
            if var_name in declared_variables:
                errors.append(f"Line {i+1}: Variable '{var_name}' redeclared")
            else:
                declared_variables.add(var_name)

        # Variable usage check (ignoring strings)
        code_without_strings = re.sub(r'"[^"]*"', '', stripped)
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code_without_strings)
        for word in words:
            if (
                word not in declared_variables
                and word not in ["int", "float", "double", "char", "printf", "if", "else", "for", "while", "return", "main", "public", "class", "static", "void", "String", "System", "out", "println", "print", "args", "stdio", "h", "include", "iostream", "using", "namespace", "std", "cout", "cin", "endl"]
            ):
                errors.append(f"Line {i+1}: Undeclared variable '{word}'")

    return errors

# ==============================
# AI SUGGESTION MODULE
# ==============================

def get_ai_suggestions(code, err_messages, api_key):
    # Hardcoded fallback logic
    hardcoded = []
    for err in err_messages:
        if "Missing semicolon" in err:
            hardcoded.append(f"Hint for {err.split(':')[0]}: Ensure the statement ends with ';'")
        elif "Unmatched opening brace" in err or "Unmatched closing brace" in err:
            hardcoded.append(f"Hint for {err.split(':')[0]}: Check your code formatting and add missing braces '{{' or '}}'")
        elif "Undeclared variable" in err:
            hardcoded.append(f"Hint for {err}: Declare the variable using its type (like 'int') before using it.")
            
    if not api_key.strip():
        hardcoded.insert(0, "[⚠️ Real AI Disabled: Provide a Gemini API Key mapped in the toolbar!]")
        return list(set(hardcoded))
        
    if not HAS_GENAI:
        return ["Error: google-generativeai module missing. Please run `pip install google-generativeai` in your terminal to unlock AI features."]
        
    try:
        client = genai.Client(api_key=api_key.strip())
        
        prompt = f"""
        I am a user in an IDE. I wrote this code:
        ```
        {code}
        ```
        And I received these compiler errors or syntax checks:
        {err_messages}
        
        Please provide a concise, distinct hint explaining what went wrong and how to cleanly fix it.
        Keep it under 3-4 sentences total. Format with simple plain text.
        """
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return [f"🤖 Gemini AI Diagnosis:", response.text.strip()]
        
    except Exception as e:
        return [f"❌ Gemini AI Connection Error:", str(e), "\nFalling back to hardcoded suggestions..."] + hardcoded

# ==============================
# OPTIMIZATION MODULE
# ==============================

def optimize_code(code):
    tips = []
    if re.search(r'for\s*\([^;]+;[^;]+;[^\)]+\)', code):
        tips.append("Optimization Tip: Consider loop unrolling if loop count is small and fixed.")
    if re.search(r'while\s*\([^)]+\)', code):
        tips.append("Optimization Tip: Ensure while loops have a clear exit condition to avoid infinite loops.")
    if len(code) > 500:
        tips.append("Optimization Tip: Large code block detected. Consider splitting into smaller functions.")
    return tips

# ==============================
# AST GENERATOR
# ==============================

def generate_ast(code):
    ast = []
    lines = code.split("\n")
    indent = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue
        
        prefix = "  " * indent
        if "}" in stripped:
            indent = max(0, indent - 1)
            prefix = "  " * indent

        if stripped.startswith("int ") or stripped.startswith("float ") or stripped.startswith("String ") or stripped.startswith("double "):
            ast.append(f"{prefix}Declaration → {stripped}")
        elif stripped.startswith("for"):
            ast.append(f"{prefix}Loop (for) → {stripped}")
            if "{" in stripped or ":" in stripped: indent += 1
        elif stripped.startswith("while"):
            ast.append(f"{prefix}Loop (while) → {stripped}")
            if "{" in stripped or ":" in stripped: indent += 1
        elif stripped.startswith("if"):
            ast.append(f"{prefix}Conditional (if) → {stripped}")
            if "{" in stripped or ":" in stripped: indent += 1
        elif stripped.startswith("else") or stripped.startswith("elif"):
            ast.append(f"{prefix}Conditional (else/elif) → {stripped}")
            if "{" in stripped or ":" in stripped: indent += 1
        elif stripped.startswith("class"):
            ast.append(f"{prefix}Class Definition → {stripped}")
            if "{" in stripped or ":" in stripped: indent += 1
        elif "public static void" in stripped or stripped.startswith("main(") or stripped.startswith("def "):
            ast.append(f"{prefix}Method Definition → {stripped}")
            if "{" in stripped or ":" in stripped: indent += 1
        elif "printf" in stripped or "System.out" in stripped or "cout" in stripped or "print" in stripped:
            ast.append(f"{prefix}Output Call → {stripped}")
        elif "=" in stripped and not stripped.startswith("int") and not stripped.startswith("float") and not stripped.startswith("String"):
            ast.append(f"{prefix}Assignment → {stripped}")
        elif "{" in stripped and not stripped.startswith("class") and not stripped.startswith("public"):
            ast.append(f"{prefix}Scope Start")
            indent += 1
        elif "}" in stripped:
            ast.append(f"{prefix}Scope End")

    return ast

# ==============================
# EXECUTION MODULE
# ==============================

def run_real_code(code, lang):
    """
    Compiles (if C/C++/Java) and executes the code via subprocess.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        if lang == "C":
            src_path = os.path.join(tmpdir, "main.c")
            exe_path = os.path.join(tmpdir, "main.exe" if os.name == 'nt' else "main")
            with open(src_path, "w") as f:
                if "#include <stdio.h>" not in code: code = "#include <stdio.h>\n" + code
                f.write(code)
            try:
                c_proc = subprocess.run(["gcc", src_path, "-o", exe_path], capture_output=True, text=True, timeout=5)
                if c_proc.returncode != 0: return f">> Real C Compilation Failed:\n{c_proc.stderr}"
                r_proc = subprocess.run([exe_path], capture_output=True, text=True, timeout=5)
                return f">> C Execution Output:\n{r_proc.stdout}\n{r_proc.stderr}"
            except FileNotFoundError: return ">> 'gcc' not found. Please install GCC to run C."
            except Exception as e: return f">> C Execution Error: {str(e)}"
                
        elif lang == "C++":
            src_path = os.path.join(tmpdir, "main.cpp")
            exe_path = os.path.join(tmpdir, "main.exe" if os.name == 'nt' else "main")
            with open(src_path, "w") as f:
                f.write(code)
            try:
                c_proc = subprocess.run(["g++", src_path, "-o", exe_path], capture_output=True, text=True, timeout=5)
                if c_proc.returncode != 0: return f">> Real C++ Compilation Failed:\n{c_proc.stderr}"
                r_proc = subprocess.run([exe_path], capture_output=True, text=True, timeout=5)
                return f">> C++ Execution Output:\n{r_proc.stdout}\n{r_proc.stderr}"
            except FileNotFoundError: return ">> 'g++' not found. Please install G++ to run C++."
            except Exception as e: return f">> C++ Error: {str(e)}"
            
        elif lang == "Java":
            class_match = re.search(r'class\s+([A-Za-z_][A-Za-z0-9_]*)', code)
            class_name = class_match.group(1) if class_match else "Main"
            if not class_match:
                if "public static void main" not in code: code = f"public class {class_name} {{\n    public static void main(String[] args) {{\n        {code}\n    }}\n}}"
                else: code = f"public class {class_name} {{\n{code}\n}}"
            src_path = os.path.join(tmpdir, f"{class_name}.java")
            with open(src_path, "w") as f: f.write(code)
            try:
                c_proc = subprocess.run(["javac", src_path], capture_output=True, text=True, timeout=5)
                if c_proc.returncode != 0: return f">> Real Java Compilation Failed:\n{c_proc.stderr}"
                r_proc = subprocess.run(["java", "-cp", tmpdir, class_name], capture_output=True, text=True, timeout=5)
                return f">> Java Execution Output:\n{r_proc.stdout}\n{r_proc.stderr}"
            except FileNotFoundError: return ">> 'javac'/'java' not found. Please install Java JDK."
            except Exception as e: return f">> Java Execution Error: {str(e)}"

        elif lang == "Python":
            src_path = os.path.join(tmpdir, "main.py")
            with open(src_path, "w") as f:
                f.write(code)
            try:
                r_proc = subprocess.run([sys.executable, src_path], capture_output=True, text=True, timeout=5)
                out = r_proc.stdout + ("\n" + r_proc.stderr if r_proc.stderr else "")
                if r_proc.returncode != 0:
                    return f">> Python Runtime Error:\n{r_proc.stderr}"
                return f">> Python Execution Output:\n{out}"
            except Exception as e: return f">> Python Error: {str(e)}"

# ==============================
# GUI DESIGN
# ==============================

class LineNumberCanvas(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.text_widget = None

    def attach(self, text_widget):
        self.text_widget = text_widget

    def redraw(self, *args):
        self.delete("all")
        if not self.text_widget: return
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(2, y, anchor="nw", text=linenum, font=("Consolas", 11), fill=THEME["line_fg"])
            i = self.text_widget.index("%s+1line" % i)

class CompilerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Language IDE (AI Powered)")
        self.root.geometry("1200x800")
        self.root.configure(bg=THEME["bg"])
        
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background=THEME["panel_bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=THEME["panel_bg"], foreground=THEME["fg"], padding=[10, 5])
        style.map("TNotebook.Tab", background=[("selected", THEME["select_bg"])])

        self.language_var = tk.StringVar(value="C")
        
        self.setup_menu()
        self.setup_layout()
        self.on_language_change()

    def setup_menu(self):
        menu_bar = tk.Menu(self.root, bg=THEME["bg"], fg=THEME["fg"])
        file_menu = tk.Menu(menu_bar, tearoff=0, bg=THEME["bg"], fg=THEME["fg"])
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menu_bar)

    def setup_layout(self):
        toolbar = tk.Frame(self.root, bg=THEME["panel_bg"], padx=10, pady=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        tk.Label(toolbar, text="Lang:", bg=THEME["panel_bg"], fg="#ffffff", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT, padx=5)
        
        # Languages now include C++ and Python
        self.lang_cb = ttk.Combobox(toolbar, textvariable=self.language_var, values=["C", "C++", "Java", "Python"], state="readonly", width=10, font=("Segoe UI", 10))
        self.lang_cb.pack(side=tk.LEFT, padx=5)
        self.lang_cb.bind("<<ComboboxSelected>>", self.on_language_change)
        
        tk.Frame(toolbar, width=30, bg=THEME["panel_bg"]).pack(side=tk.LEFT)
        
        compile_btn = tk.Button(toolbar, text="▶ Compile & Analyze", command=self.compile_code, bg=THEME["button_bg"], fg=THEME["button_fg"], relief=tk.FLAT, padx=10, font=("Segoe UI", 10, "bold"))
        compile_btn.pack(side=tk.LEFT, padx=5)
        
        run_btn = tk.Button(toolbar, text="🏃 Run Code", command=self.run_code, bg="#28a745", fg=THEME["button_fg"], relief=tk.FLAT, padx=10, font=("Segoe UI", 10, "bold"))
        run_btn.pack(side=tk.LEFT, padx=5)
        
        # AI API KEY Area
        tk.Label(toolbar, text="Gemini API Key:", bg=THEME["panel_bg"], fg="#ffdf00", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(40, 5))
        self.api_key_var = tk.StringVar()
        self.api_key_entry = tk.Entry(toolbar, textvariable=self.api_key_var, show="*", width=25, font=("Segoe UI", 10))
        self.api_key_entry.pack(side=tk.LEFT, padx=5)
        
        help_btn = tk.Button(toolbar, text="?", command=self.show_api_help, bg="#569cd6", fg="#ffffff", relief=tk.FLAT, font=("Segoe UI", 8, "bold"))
        help_btn.pack(side=tk.LEFT, padx=2)

        # PanedWindow
        paned = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashwidth=5, bg=THEME["panel_bg"])
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Code Area
        code_frame = tk.Frame(paned, bg=THEME["bg"])
        paned.add(code_frame, minsize=300)

        self.line_numbers = LineNumberCanvas(code_frame, width=40, bg=THEME["line_bg"], highlightthickness=0)
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        self.code_input = scrolledtext.ScrolledText(code_frame, bg=THEME["bg"], fg=THEME["fg"], insertbackground=THEME["cursor"], font=("Consolas", 12), undo=True, borderwidth=0)
        self.code_input.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.line_numbers.attach(self.code_input)

        self.code_input.bind("<KeyRelease>", self.on_key_release)
        self.code_input.bind("<Return>", self.on_key_release)
        self.code_input.bind("<MouseWheel>", self.on_key_release)

        # Output Area
        self.notebook = ttk.Notebook(paned)
        paned.add(self.notebook, minsize=200)

        self.tab_output = self.create_text_tab("Terminal", self.notebook)
        self.tab_errors = self.create_text_tab("Errors & Suggestions", self.notebook)
        self.tab_ast = self.create_text_tab("AST", self.notebook)
        self.tab_tokens = self.create_text_tab("Tokens", self.notebook)

        self.notebook.add(self.tab_output, text="Terminal")
        self.notebook.add(self.tab_errors, text="Errors & Suggestions 🤖")
        self.notebook.add(self.tab_ast, text="AST")
        self.notebook.add(self.tab_tokens, text="Tokens")

    def show_api_help(self):
        msg = (
            "To get a FREE Gemini API Key:\n\n"
            "1. Visit: https://aistudio.google.com/app/apikey\n"
            "2. Sign in with your Google account.\n"
            "3. Click 'Create API key' (you don't need a billing account, it's free).\n"
            "4. Copy the generated key and paste it into the textbox in the toolbar.\n\n"
            "Once pasted, your compiler errors and code will be sent to Gemini for real AI diagnostic suggestions!"
        )
        messagebox.showinfo("Get Gemini API Key", msg)

    def on_language_change(self, event=None):
        lang = self.language_var.get()
        self.code_input.delete("1.0", tk.END)
        
        if lang == "C":
            sample_code = "#include <stdio.h>\n\nint main() {\n    int a = 10;\n    float b = 20.5;\n    printf(\"Hello World! %d\\n\", a);\n    return 0;\n}\n"
        elif lang == "C++":
            sample_code = "#include <iostream>\nusing namespace std;\n\nint main() {\n    int a = 10;\n    cout << \"Hello World! \" << a << endl;\n    return 0;\n}\n"
        elif lang == "Java":
            sample_code = "public class Main {\n    public static void main(String[] args) {\n        int a = 10;\n        System.out.println(\"Hello World! \" + a);\n    }\n}\n"
        elif lang == "Python":
            sample_code = "def main():\n    a = 10\n    print(f\"Hello World! {a}\")\n\nif __name__ == \"__main__\":\n    main()\n"
            
        self.code_input.insert("1.0", sample_code)
        self.highlight_syntax()
        self.line_numbers.redraw()

    def create_text_tab(self, name, parent):
        return scrolledtext.ScrolledText(parent, bg=THEME["bg"], fg=THEME["fg"], font=("Consolas", 11), borderwidth=0, state=tk.DISABLED)

    def write_to_tab(self, tab, text, clear=True):
        tab.config(state=tk.NORMAL)
        if clear: tab.delete("1.0", tk.END)
        tab.insert(tk.END, text + "\n")
        tab.config(state=tk.DISABLED)

    def on_key_release(self, event=None):
        self.highlight_syntax()
        self.line_numbers.redraw()

    def highlight_syntax(self):
        self.code_input.tag_configure("KEYWORD", foreground=THEME["keyword"])
        self.code_input.tag_configure("NUMBER", foreground=THEME["number"])
        self.code_input.tag_configure("STRING", foreground=THEME["string"])
        self.code_input.tag_configure("COMMENT", foreground=THEME["comment"])

        code = self.code_input.get("1.0", "end-1c")
        
        for tag in ["KEYWORD", "NUMBER", "STRING", "COMMENT"]:
            self.code_input.tag_remove(tag, "1.0", tk.END)

        # Apply Comments (Regex covers // and #)
        for match in re.finditer(r'(//|#).*', code):
            start_index = f"1.0 + {match.start()} chars"
            end_index = f"1.0 + {match.end()} chars"
            self.code_input.tag_add("COMMENT", start_index, end_index)

        for token_type, pattern in TOKENS:
            if token_type not in ["KEYWORD", "NUMBER", "STRING"]:
                continue
            for match in re.finditer(pattern, code):
                start_index = f"1.0 + {match.start()} chars"
                end_index = f"1.0 + {match.end()} chars"
                if "COMMENT" not in self.code_input.tag_names(start_index):
                    self.code_input.tag_add(token_type, start_index, end_index)

    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Source Files", "*.c;*.cpp;*.java;*.py"), ("All Files", "*.*")])
        if file_path:
            if file_path.endswith(".java"): self.language_var.set("Java")
            elif file_path.endswith(".c"): self.language_var.set("C")
            elif file_path.endswith(".cpp"): self.language_var.set("C++")
            elif file_path.endswith(".py"): self.language_var.set("Python")
                
            with open(file_path, "r") as file:
                self.code_input.delete("1.0", tk.END)
                self.code_input.insert(tk.END, file.read())
                self.highlight_syntax()
                self.line_numbers.redraw()

    def save_file(self):
        ext_map = {"C": ".c", "C++": ".cpp", "Java": ".java", "Python": ".py"}
        ext = ext_map.get(self.language_var.get(), ".txt")
        file_path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[(f"{self.language_var.get()} Files", f"*{ext}"), ("All Files", "*.*")])
        if file_path:
            with open(file_path, "w") as file:
                file.write(self.code_input.get("1.0", tk.END))

    def compile_code(self):
        code = self.code_input.get("1.0", tk.END)
        lang = self.language_var.get()
        
        tokens = tokenize(code)
        tok_str = "\n".join([f"{t[0]}: {t[1]}" for t in tokens])
        self.write_to_tab(self.tab_tokens, tok_str)

        # Regex Syntax & Semantic checks
        syn_err = check_syntax(code, lang)
        sem_err = semantic_analysis(code, lang)
        all_err = syn_err + sem_err
        
        if all_err:
            key = self.api_key_var.get()
            self.write_to_tab(self.tab_errors, "Pinging AI for suggestions... 📡", clear=True)
            self.root.update()
            
            suggestions = get_ai_suggestions(code, all_err, key)
            err_str = "STRUCTURAL ERRORS DETECTED:\n- " + "\n- ".join(all_err) + "\n\n" + "-"*40 + "\n\n" + "\n\n".join(suggestions)
            self.write_to_tab(self.tab_errors, err_str)
            self.notebook.select(self.tab_errors)
        else:
            self.write_to_tab(self.tab_errors, "✅ No Syntax or Semantic Errors Found!")
            self.notebook.select(self.tab_ast)

        ast = generate_ast(code)
        self.write_to_tab(self.tab_ast, "\n".join(ast) if ast else "No AST could be generated.")

        if not all_err:
            self.write_to_tab(self.tab_output, f"[{lang}] Compilation Pre-checks Successful! Press Run to execute.", clear=True)

    def run_code(self):
        # We always attempt run even if syntax checks complain slightly, real compilers are the ultimate truth.
        self.write_to_tab(self.tab_output, "Executing pipeline...", clear=True)
        self.root.update()

        code = self.code_input.get("1.0", tk.END)
        lang = self.language_var.get()
        key = self.api_key_var.get()
        
        output = run_real_code(code, lang)
        
        # If real runtime errors occur, ask Gemini for help!
        if ("Error" in output or "Failed" in output) and key.strip() and HAS_GENAI:
            self.write_to_tab(self.tab_output, output + "\n\n🔄 Querying Gemini AI for crash diagnostic... please wait...", clear=True)
            self.root.update()
            
            try:
                client = genai.Client(api_key=key.strip())
                prompt = f"The user ran this {lang} code:\n{code}\n\nAnd it crashed with this compiler/runtime output:\n{output}\n\nCan you briefly explain why it crashed and precisely what they should change?"
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                
                ai_footer = f"\n\n🤖 --- GEMINI AI DIAGNOSTIC ---\n{resp.text.strip()}\n-----------------------------"
                self.write_to_tab(self.tab_output, output + ai_footer, clear=True)
            except Exception as e:
                self.write_to_tab(self.tab_output, output + f"\n\n[Failed to fetch AI diagnostics: {str(e)}]", clear=True)
        else:
            self.write_to_tab(self.tab_output, output, clear=True)
            
        self.notebook.select(self.tab_output)

if __name__ == "__main__":
    root = tk.Tk()
    app = CompilerApp(root)
    root.mainloop()