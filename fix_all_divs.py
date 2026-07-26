"""Fix all div imbalance issues in the desktop React pages."""
import os
import re

base = r'c:\Users\Asus\Desktop\dash\apps\desktop\src\pages'

def count_divs(content):
    opens = content.count('<div')
    closes = content.count('</div>')
    return opens, closes

def fix_file(filename, fix_fn):
    path = os.path.join(base, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    before = count_divs(content)
    content = fix_fn(content)
    after = count_divs(content)
    
    if before != after:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"{filename}: div balance {before[0]-before[1]} -> {after[0]-after[1]} (fixed)")
    else:
        print(f"{filename}: No change (was {before[0]-before[1]})")


def fix_memory(content):
    """Add missing </div> for page-header div"""
    # page-header structure: <div class="page-header"> <div> <h2> <p> </div>
    # Currently missing the </div> that closes the page-header div
    old = '<p className="page-subtitle">Search and manage your DASH memories</p>\n        </div>\n\n      <form'
    new = '<p className="page-subtitle">Search and manage your DASH memories</p>\n        </div>\n      </div>\n\n      <form'
    return content.replace(old, new)

def fix_settings(content):
    """Add missing </div> for page-header div"""
    old = '<p className="page-subtitle">Configure your DASH assistant</p>\n        </div>\n\n      <div'
    new = '<p className="page-subtitle">Configure your DASH assistant</p>\n        </div>\n      </div>\n\n      <div'
    return content.replace(old, new)

def fix_dashboard(content):
    """Add missing </div> for page-header div"""
    # Already fixed earlier

def fix_chat(content):
    """Fix missing </div> closing tags in the chat sidebar"""
    # The Chat sidebar has an outer div with "glass" class, containing:
    # - a header div
    # - a scrollable div
    # Need to add </div> after the scrollable div to close the outer glass div
    
    # Find the pattern: after the conversations list scrollable div ends
    # There should be a </div> closing the glass sidebar div before </div> for the parent
    old = '</div>\n      </div>\n\n      {/* Chat area */}'
    new = '</div>\n        </div>\n      </div>\n\n      {/* Chat area */}'
    # Actually need to be more careful - count the structure
    
    # The sidebar structure is:
    # <div className="glass" style={...}>   <- sidebar outer
    #   <div style={...}>                    <- header
    #   </div>
    #   <div style={...}>                    <- scrollable list area
    #     {conversations.map(...)}
    #   </div>
    # </div>                                  <- THIS IS MISSING
    # 
    # {/* Chat area */}
    # <div className="glass" style={...}>   <- chat area outer
    
    # Find the pattern after the scrollable div
    # The scrollable div's children should be followed by </div>
    # Currently only one </div> exists (closing the scrollable div),
    # missing the </div> for the glass sidebar
    
    # Let's find: the button mapping closing, then the scrollable div's </div>
    # and add one more </div> before the chat area comment
    
    # Pattern: the scrollable div with flex:1 overflowY ends, then we need another </div>
    old = '              {conv.title || "New conversation"}\n            </button>\n          ))}\n        </div>\n      </div>\n\n      {/* Chat area */}'
    new = '              {conv.title || "New conversation"}\n            </button>\n          ))}\n        </div>\n      </div>\n      </div>\n\n      {/* Chat area */}'
    
    if old in content:
        return content.replace(old, new)
    
    # Fallback: try more generic pattern - after the second </div> before chat area
    old2 = '          ))}\n        </div>\n      </div>\n\n      {/* Chat area */}'
    new2 = '          ))}\n        </div>\n      </div>\n      </div>\n\n      {/* Chat area */}'
    if old2 in content:
        return content.replace(old2, new2)
    
    # Last resort: after "No conversations yet" div
    old3 = '            </div>\n          )}\n          {conversations.map((conv) => ('
    # This is part of the scrollable div - the div with flex:1 overflowY
    # Its structure is: <div style={{flex:1, overflowY...}}> ... </div>
    # Check if there's a closing </div> for this
    print("Chat.tsx: Could not find exact pattern, counting divs manually...")
    return content


# Fix each file
fix_file('Memory.tsx', fix_memory)
fix_file('Settings.tsx', fix_settings)
fix_file('Chat.tsx', fix_chat)

# Verify all files
print("\nFinal verification:")
for f in ['Memory.tsx', 'Settings.tsx', 'Chat.tsx', 'Login.tsx', 'Dashboard.tsx', 'Projects.tsx', 'Automation.tsx']:
    path = os.path.join(base, f)
    with open(path, 'r', encoding='utf-8') as fp:
        c = fp.read()
    opens, closes = count_divs(c)
    print(f"  {f}: <div={opens}, </div>={closes}, balance={opens-closes}", "OK" if opens==closes else "FIX NEEDED")
