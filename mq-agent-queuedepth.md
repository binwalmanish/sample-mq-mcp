# MQ Client - Use the followiong for MQ queue depth which you can ask Agent to check

1. Decrease the queue depth to 5 or 10, default queue depth is 5000
2. Write 10 message to the queue
3. Ask AI agent to check the queue depth or check the issues
4. It should answer that queue depth is high, start the reader application which can read the messages.