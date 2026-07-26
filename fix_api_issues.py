"""Fix all remaining API and frontend compatibility issues."""
import re, os

def fix_api_ts():
    """Fix api.ts mismatches with backend endpoints."""
    path = r'c:\Users\Asus\Desktop\dash\apps\desktop\src\lib\api.ts'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    
    changes = []
    
    # Fix 1: memory.search - backend returns {items: [...], query: '...'}
    old = 'request<Array<{ id: string; content: string; type: string; score: number }>>(`/memory/search?q=${encodeURIComponent(query)}`)'
    new = 'request<{ items: Array<{ id: string; content: string; type: string; score: number }>; query: string }>(`/memory/search?q=${encodeURIComponent(query)}`)'
    if old in c:
        c = c.replace(old, new)
        changes.append("Fixed memory.search return type to match backend")
    
    # Fix 2: auth.register has inconsistent spacing before request
    old2 = '  request("/auth/register", {'
    new2 = '  request("/auth/register", {'
    if old2 in c:
        c = c.replace(old2, new2)
    
    if changes:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c)
    
    for ch in changes:
        print(f"api.ts: {ch}")
    return changes

def fix_memory_search():
    """Fix Memory.tsx search to handle wrapped backend response."""
    path = r'c:\Users\Asus\Desktop\dash\apps\desktop\src\pages\Memory.tsx'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    
    # Fix: search returns {items: [...]} not raw array
    old = '      const results = await memoryApi.search(searchQuery);\n      setSearchResults(results);'
    new = '      const result = await memoryApi.search(searchQuery);\n      setSearchResults(result.items);'
    
    if old in c:
        c = c.replace(old, new)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c)
        print("Memory.tsx: Fixed search to use result.items wrapper")
        return True
    
    # Check current state
    idx = c.find('search(searchQuery)')
    print(f"Memory.tsx search call context: {repr(c[idx:idx+100])}")
    return False

def fix_auth_store():
    """Fix authStore to reset WS client on logout."""
    path = r'c:\Users\Asus\Desktop\dash\apps\desktop\src\stores\authStore.ts'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    
    # Add WS reset on logout
    old = "  logout: () => {\n    localStorage.removeItem(\"dash_access_token\");\n    localStorage.removeItem(\"dash_refresh_token\");\n    set({ user: null, isAuthenticated: false, isLoading: false });\n  },"
    new = "  logout: () => {\n    localStorage.removeItem(\"dash_access_token\");\n    localStorage.removeItem(\"dash_refresh_token\");\n    try {\n      const { resetWsClient } = require(\"@/lib/wsClient\");\n      resetWsClient();\n    } catch {}\n    set({ user: null, isAuthenticated: false, isLoading: false });\n  },"
    
    if old in c:
        c = c.replace(old, new)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c)
        print("authStore.ts: Added WS client reset on logout")
    else:
        # Try with dynamic import pattern instead
        old2 = "  logout: () => {\n    localStorage.removeItem(\"dash_access_token\");\n    localStorage.removeItem(\"dash_refresh_token\");"
        new2 = "  logout: () => {\n    localStorage.removeItem(\"dash_access_token\");\n    localStorage.removeItem(\"dash_refresh_token\");\n    try {\n      const { resetWsClient } = require(\"@/lib/wsClient\");\n      resetWsClient();\n    } catch {}\n    set({ user: null, isAuthenticated: false, isLoading: false });"
        
        if old2 in c:
            c = c.replace(old2, new2)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(c)
            print("authStore.ts: Added WS client reset on logout (alt pattern)")
        else:
            idx = c.find('logout:')
            if idx >= 0:
                print(f"authStore.ts logout current state: {repr(c[idx:idx+300])}")

def verify_all_files():
    """Check all pages for common issues."""
    base = r'c:\Users\Asus\Desktop\dash\apps\desktop\src\pages'
    files = ['Memory.tsx', 'Settings.tsx', 'Chat.tsx', 'Login.tsx', 'Dashboard.tsx', 'Projects.tsx', 'Automation.tsx']
    
    for f in files:
        path = os.path.join(base, f)
        with open(path, 'r', encoding='utf-8') as fp:
            c = fp.read()
        
        opens = len(re.findall(r'<div[^>]*>', c))
        closes = len(re.findall(r'</div>', c))
        self_closing = len(re.findall(r'<div[^>]*/>', c))
        balance = opens - closes - self_closing
        
        # Check for common issues
        issues = []
        if balance != 0:
            issues.append(f'div imbalance: {balance}')
        if 'console.error' in c:
            # Check each console.error call
            idx = 0
            while True:
                idx = c.find('console.error', idx)
                if idx == -1:
                    break
                line = c[:idx].count('\n') + 1
                issues.append(f'console.error on line {line}')
                idx += 1
        
        status = 'OK' if not issues else '; '.join(issues)
        print(f'{f}: bal={balance} {status}')

if __name__ == '__main__':
    fix_api_ts()
    fix_memory_search()
    fix_auth_store()
    print('\nVerification:')
    verify_all_files()
