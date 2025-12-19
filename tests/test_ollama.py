"""Ollama 연결 테스트"""
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

print("🧪 Ollama 연결 테스트 중...")

try:
    response = client.chat.completions.create(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": "Hello! Just say 'Hi' in one word."}],
        temperature=0.7,
        max_tokens=10
    )
    print(f"✅ 응답: {response.choices[0].message.content}")
    print("✅ Ollama 정상 작동!")
except Exception as e:
    print(f"❌ 오류: {e}")
