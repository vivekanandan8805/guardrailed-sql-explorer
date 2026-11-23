
import os
from groq import Groq

# Read the API key from the environment
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError(
        "GROQ_API_KEY is missing. Set it in PowerShell first."
    )

# Connect to Groq
client = Groq(api_key=api_key)

# Send a test question
response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {
            "role": "user",
            "content": "Explain what a database is in one simple sentence."
        }
    ]
)

# Print the response
print("\nGroq response:")
print(response.choices[0].message.content)
