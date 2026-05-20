from dotenv import load_dotenv
load_dotenv()

import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI

async def test():
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    res = await llm.ainvoke("Say hello!")
    print("Response:", res.content)

if __name__ == "__main__":
    asyncio.run(test())
