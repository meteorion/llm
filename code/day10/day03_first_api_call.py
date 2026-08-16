"""
Day 3：第一次调用模型 API
实现目标：发送一句话，打印模型回复

实现步骤：
1. 加载环境变量，读取 API Key
2. 配置请求参数（base_url、model、temperature）
3. 构造消息体（messages 列表）
4. 发送 HTTP 请求 / 调用 SDK
5. 解析响应，提取回复内容
6. 打印结果，记录 Token 用量
"""
import os
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")

def call_llm_with_requests(prompt: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    data = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7
    }

    url = f"{BASE_URL}/chat/completions"

    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code} - {response.text}")

    result = response.json()
    return result["choices"][0]["message"]["content"]

def call_llm_with_openapi(prompt: str) -> str | None:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    result = client.chat.completions.create(
        model=f"{MODEL}",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return result.choices[0].message.content


def main():
    prompt = "你好，请用一句话介绍诸葛亮"
    print(f"用户：{prompt}")

    try:
        reply = call_llm_with_openapi(prompt)
        print(f"助手：{reply}")
    except Exception as e:
        print(f"错误： {e}")

if __name__ == "__main__":
    main()