# Comprehensive Document Guide

## Introduction
This document demonstrates the full capabilities of the **md2star** pipeline for generating `.docx` artifacts. 

The title extraction automatically removed the `# Comprehensive Document Guide` header above and converted it to the literal document Title metadata. Subtitles containing the Author and Date were also injected dynamically right below it using Lua scripts. 

## 1. List Formatting and Alignment
Users often accidentally construct tight, "glued" lists in Markdown. Our Python preprocessor mathematically expands these into safe loose lists so Pandoc renders correct document bullets.

A standard unordered list representing corporate sectors:
- Information Technology
- Sales and Marketing
- Research & Development 

An ordered workflow list:
1. Initialize the target objective.
2. Draft the research design.
3. Validate metrics.

## 2. Mermaid Diagram rendering
Using Kroki, we can safely embed system architecture diagrams straight into documents without breaking Pandoc:

```mermaid
graph LR;
    User[Markdown User] --> Engine{Preprocessing}
    Engine --> |Mermaid API| Image(Locally Cached PNG)
    Engine --> Engine2[Pandoc AST Hook]
    Engine2 --> Final[Microsoft Word DOCX]
```

## 3. Mathematical Typesetting
Equations written in $\LaTeX$ are flawlessly mapped onto Microsoft Office's native equation engine:

$$
e^{i \times \pi}+1 = 0
$$

and

$$
f(x) = \int_{-\infty}^{\infty} \hat{f}(\xi)\,e^{2 \pi i \xi x} \,d\xi
$$

## 4. Rich Media & Tables
You can securely embed tables seamlessly for data representations:

| Model Architecture | Parameter Count | Release Year |
|--------------------|-----------------|--------------|
| GPT-4             | Undisclosed     | 2023         |
| Llama 3           | 70 Billion      | 2024         |
| Open Weights      | 8 Billion       | 2024         |

You can also embed standard images via URL paths:
![](https://picsum.photos/800/400)

## 5. Professional Citations
When compiled using `--bib references.bib --bibliography-name "References"`, native references like [@causality-pearl] will be automatically evaluated, parsed via `citeproc`, and structured beautifully inside the output.
