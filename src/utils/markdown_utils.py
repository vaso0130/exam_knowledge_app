import re
from typing import Dict, Any

def format_code_blocks(text: str) -> str:
    """
    Detects code blocks in the given text, attempts to identify the language,
    and ensures proper Markdown formatting with syntax highlighting.
    """
    def replace_code_block(match):

        lang_specifier = match.group(1)
        code_content = match.group(2)

        lang = lang_specifier if lang_specifier else guess_programming_language(code_content)

        return f"""``` {lang}
{code_content}```"""

    # Regex to find code blocks.
    # It captures the language specifier (optional) and then all content until the closing ```
    # The `re.DOTALL` flag allows '.' to match newlines.
    # We make the newline after the language specifier part of the content capture.
    # Require a newline after the optional language specifier to avoid
    # incorrectly treating the first line of code as the language.
    pattern = r"```\s*(\w+)?\n([\s\S]*?)```"
    return re.sub(pattern, replace_code_block, text)

def guess_programming_language(code: str) -> str:
    """
    Attempts to guess the programming language of a given code snippet.
    This is a very basic heuristic and can be expanded.
    """
    code = code.strip().lower()

    if not code:
        return ""

    # Python keywords
    if re.search(r"def |import |print\(|self\.|elif |for |while |class |async |await ", code):
        return "python"
    # C/C++ keywords
    if re.search(r"#include|<iostream>|int main\(|printf\(|std::cout|void |class |struct |new |delete |nullptr ", code):
        return "c"
    # Pseudocode indicators
    if re.search(r"algorithm|begin|end|read|write|if then else|for each|while do|function |procedure |return ", code):
        return "pseudocode"
    # JavaScript keywords
    if re.search(r"function |const |let |var |console\.log\(|document\.getelementbyid|=> |async |await |import |export |class ", code):
        return "javascript"
    # Java keywords
    if re.search(r"public class |static void main|system\.out\.println|import |package |new |try |catch |finally ", code):
        return "java"
    # SQL keywords
    if re.search(r"select |from |where |insert into |update |delete from|create table |alter table |join |group by |order by ", code):
        return "sql"
    # HTML indicators
    if re.search(r"<html|<body|<div|<p|<a href|<script|<style|<head|<title ", code):
        return "html"
    # CSS indicators
    if re.search(r"body \{|\.class \{|#id \{|color:|font-size:|background-color:|display:|padding:|margin: ", code):
        return "css"
    # PHP indicators
    if re.search(r"<\?php|echo |\$this->|function |class |namespace |use |require |include ", code):
        return "php"
    # Ruby indicators
    if re.search(r"def |end |puts |require |class |module |do |if |unless ", code):
        return "ruby"
    # Go indicators
    if re.search(r"package main|func main|fmt\.println|import |var |const |type |struct |interface ", code):
        return "go"
    # Swift indicators
    if re.search(r"import swift|func |var |let |print\(|class |struct |enum |protocol ", code):
        return "swift"
    # Kotlin indicators
    if re.search(r"fun main|println\(|var |val |class |object |interface |import |package ", code):
        return "kotlin"
    # Rust indicators
    if re.search(r"fn main|println!|let mut|struct |enum |impl |trait |mod |use ", code):
        return "rust"
    # Shell script indicators
    if re.search(r"#!/bin/bash|echo |if \[|for i in|fi |esac |case |while |do |done ", code):
        return "bash"
    # JSON indicators
    if re.search(r"\{|\}|\[|\]|\"\\w+\": ", code):
        return "json"
    # XML indicators
    if re.search(r"<\?xml|<root>|<element attribute=\"value\"> ", code):
        return "xml"
    # Markdown indicators (basic)
    if re.search(r"^#+ |^- |^\* |^> |^``` ", code, re.MULTILINE):
        return "markdown"

    return "text" # Default to text if not recognized

def format_summary_to_markdown(summary_data: Dict[str, Any]) -> str:
    """
    將AI生成的摘要JSON數據轉換為結構化的Markdown格式。
    """
    markdown_output = []

    if not summary_data:
        return ""

    # 總結 (summary)
    if "summary" in summary_data and summary_data["summary"]:
        markdown_output.append(f"## 總結\n\n{summary_data["summary"]}\n")

    # 核心概念 (key_concepts)
    if "key_concepts" in summary_data and isinstance(summary_data["key_concepts"], list):
        if summary_data["key_concepts"]:
            markdown_output.append("## 核心概念\n")
            for concept in summary_data["key_concepts"]:
                if isinstance(concept, dict) and "name" in concept and "description" in concept:
                    markdown_output.append(f"- **{concept["name"]}**: {concept["description"]}")
                elif isinstance(concept, str):
                    markdown_output.append(f"- {concept}")
            markdown_output.append("") # Add a newline for spacing

    # 技術術語 (technical_terms)
    if "technical_terms" in summary_data and isinstance(summary_data["technical_terms"], list):
        if summary_data["technical_terms"]:
            markdown_output.append("## 技術術語\n")
            for term in summary_data["technical_terms"]:
                if isinstance(term, dict) and "name" in term and "description" in term:
                    markdown_output.append(f"- **{term["name"]}**: {term["description"]}")
                elif isinstance(term, str):
                    markdown_output.append(f"- {term}")
            markdown_output.append("")

    # 分類資訊 (classification_info)
    if "classification_info" in summary_data and isinstance(summary_data["classification_info"], list):
        if summary_data["classification_info"]:
            markdown_output.append("## 分類資訊\n")
            for info in summary_data["classification_info"]:
                if isinstance(info, dict) and "name" in info and "description" in info:
                    markdown_output.append(f"- **{info["name"]}**: {info["description"]}")
                elif isinstance(info, str):
                    markdown_output.append(f"- {info}")
            markdown_output.append("")

    # 實務應用 (practical_applications)
    if "practical_applications" in summary_data and isinstance(summary_data["practical_applications"], list):
        if summary_data["practical_applications"]:
            markdown_output.append("## 實務應用\n")
            for app in summary_data["practical_applications"]:
                if isinstance(app, dict) and "name" in app and "description" in app:
                    markdown_output.append(f"- **{app["name"]}**: {app["description"]}")
                elif isinstance(app, str):
                    markdown_output.append(f"- {app}")
            markdown_output.append("")

    # 條列式重點 (bullets)
    if "bullets" in summary_data and isinstance(summary_data["bullets"], list):
        if summary_data["bullets"]:
            markdown_output.append("## 條列式重點\n")
            for bullet in summary_data["bullets"]:
                markdown_output.append(f"- {bullet}")
            markdown_output.append("")

    return "\n".join(markdown_output).strip()
