#!/usr/bin/env python3
"""
preprocessing.py

Applies transformations to the input Markdown before passing it to Pandoc.
Currently, this ensures that list items have a preceding blank line.
This fixes markdown lists not rendering when glued to the preceding text
and spaces out list items (changing tight lists to loose lists for better readability).
"""

import sys
import re
import os
import tempfile

def preprocess_markdown(content: str) -> str:
    lines = content.split('\n')
    out_lines = []
    in_code_block = False
    
    # Matches a list item: optional space, then -, *, +, or 1., 2., etc., followed by space
    list_pattern = re.compile(r'^(\s*(?:[-*+]|\d+\.)\s+.*)')
    
    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            out_lines.append(line)
            continue
            
        if in_code_block:
            out_lines.append(line)
            continue
            
        match = list_pattern.match(line)
        if match:
            # Add an empty line before a list item if the previous line is NOT empty
            if out_lines and out_lines[-1].strip() != '':
                out_lines.append('')
        
        out_lines.append(line)
        
    return '\n'.join(out_lines)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 preprocessing.py <input.md>")
        sys.exit(1)
        
    in_path = sys.argv[1]
    
    with open(in_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    processed = preprocess_markdown(content)
    
    # Write to a temp file in the same directory to keep relative paths intact
    dir_name = os.path.dirname(os.path.abspath(in_path))
    fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix='.md', prefix='.preprocessed_')
    
    with os.fdopen(fd, 'w', encoding='utf-8') as temp_file:
        temp_file.write(processed)
        
    # Output the temp file path so the wrapper shell script knows where it is
    print(temp_path)
