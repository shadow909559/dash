import sys  
content = open('desktop\\src\\pages\\Dashboard.tsx', 'r', encoding='utf-8').read()  
content = content.replace('Conversations\x0a          \x3c/div\x3e\x0a\x0a        \x3cdiv','Conversations\x0a          \x3c/div\x3e\x0a        \x3c/div\x3e\x0a\x0a        \x3cdiv')  
open('desktop\\src\\pages\\Dashboard.tsx', 'w', encoding='utf-8').write(content)  
print('ok') 
