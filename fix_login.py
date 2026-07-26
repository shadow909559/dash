import base64

# Write Login.tsx without tag stripping issues

content = '''import { useState, FormEvent } from "react";
import { useAuthStore } from "@/stores/authStore";
import AnimatedBackground from "@/components/AnimatedBackground";

export default function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const { login, register, isLoading, error, clearError } = useAuthStore();

  ''' + chr(97) + chr(115) + chr(121) + chr(110) + chr(99) + ''' ''' + chr(102) + chr(117) + chr(110) + chr(99) + chr(116) + chr(105) + chr(111) + chr(110) + ''' ''' + chr(104) + chr(97) + chr(110) + chr(100) + chr(108) + chr(101) + chr(83) + chr(117) + chr(98) + chr(109) + chr(105) + chr(116) + '''(e: FormEvent) {
    e.preventDefault();
    clearError();
    try {
      if (isRegister) {
        // Register then login (register now returns tokens, but store handles it)
        await register(email, password, username || undefined);
        await login(email, password);
      } else {
        await login(email, password);
      }
    } catch {
      // error is set in store
    }
  }
'''

with open('c:/Users/Asus/Desktop/dash/apps/desktop/src/pages/Login.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Written Login.tsx")
