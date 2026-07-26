import os

# Fix Memory.tsx - restore missing useEffect line
path = r'c:\Users\Asus\Desktop\dash\apps\desktop\src\pages\Memory.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the missing useEffect line - the edit_file tool stripped it
old = "  const [isLoading, setIsLoading] = useState(true);\n\n\n  }, [page]);"
new = "  const [isLoading, setIsLoading] = useState(true);\n\n  useEffect(() => {\n    loadMemories();\n  }, [page]);"

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Memory.tsx: Fixed missing useEffect line")
else:
    print("Memory.tsx: Pattern not found")
    # Debug: show the area
    idx = content.find("useState(true)")
    if idx >= 0:
        print(repr(content[idx:idx+150]))

# Count div balance
opens = content.count('<div')
has_slash = content.count('</div>')
print(f"Memory.tsx divs: <div={opens}, </div>={has_slash}, balanced={opens==has_slash}")

# Fix Dashboard.tsx - add missing </div> after page-subtitle
path2 = r'c:\Users\Asus\Desktop\dash\apps\desktop\src\pages\Dashboard.tsx'
with open(path2, 'r', encoding='utf-8') as f:
    content2 = f.read()

# Check div balance
opens2 = content2.count('<div')
closes2 = content2.count('</div>')
print(f"Dashboard.tsx divs: <div={opens2}, </div>={closes2}, diff={opens2 - closes2}")

# Fix: add missing closing </div> for the page-header's inner div
# The structure should be:
# <div className="page-header">
#   <div>
#     <h2>...</h2>
#     <p>...</p>
#   </div>    <-- this was missing
# </div>     <-- this was missing

old2 = '          <p className="page-subtitle">Overview of your DASH assistant</p>\n        </div>\n\n      <div className="grid-4"'
new2 = '          <p className="page-subtitle">Overview of your DASH assistant</p>\n        </div>\n      </div>\n\n      <div className="grid-4"'

if old2 in content2:
    content2 = content2.replace(old2, new2)
    with open(path2, 'w', encoding='utf-8') as f:
        f.write(content2)
    print("Dashboard.tsx: Fixed missing </div>")
else:
    print("Dashboard.tsx: Pattern not found")
    idx2 = content2.find('page-subtitle')
    if idx2 >= 0:
        print(repr(content2[idx2:idx2+200]))

# Re-check
opens2 = content2.count('<div')
closes2 = content2.count('</div>')
print(f"Dashboard.tsx after fix: <div={opens2}, </div>={closes2}, diff={opens2 - closes2}")

print("\nDone!")
