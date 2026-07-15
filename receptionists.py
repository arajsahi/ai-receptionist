from flask import Flask, render_template_string, request, redirect , url_for
import anthropic
import os
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
BUSINESS_INFO = """
You are a friendly receptionist for Smile Dental Clinic.

Clinic information:
- Hours: Monday to Friday 9am-5pm, Saturday 10am-2pm, closed Sunday
- Services: check-ups, cleaning ($120), fillings ($200), whitening ($350)
- Address: 123 Main Street, Toronto
- For emergencies, we keep same-day slots open

Your job:
- Answer questions politely and briefly
- Help book appointments
- If someone wants to book, ask for their name, preferred day, and phone number
- Keep replies short and warm, like a real receptionist on the phone
"""

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Smile Dental - AI Receptionist</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; background: #f5f5f5; padding: 20px; }
  h1 { color: #2c3e50; }
  .chat { background: white; padding: 20px; border-radius: 10px; min-height: 300px; margin-bottom: 15px; }
  .user { text-align: right; margin: 10px 0; }
  .user span { background: #2c3e50; color: white; padding: 8px 14px; border-radius: 12px; display: inline-block; }
  .ai { text-align: left; margin: 10px 0; }
  .ai span { background: #ecf0f1; padding: 8px 14px; border-radius: 12px; display: inline-block; }
  input[type=text] { width: 75%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; }
  button { background: #2c3e50; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; }
</style>
</head>
<body>
<h1>🦷 Smile Dental Clinic</h1>
<div class="chat">
  {% for msg in history %}
    <div class="{{ msg.role }}"><span>{{ msg.text }}</span></div>
  {% endfor %}
</div>
<form method="POST">
  <input type="text" name="message" placeholder="Type your message..." autofocus>
  <button type="submit">Send</button>
</form>
</body>
</html>
"""
conversation=[]

@app.route("/",methods=["GET","POST"])
def index():
    if request.method == "POST":
        user_message = request.form.get("message","").strip()
        if not user_message:
            return redirect(url_for("index"))
        conversation.append({"role":"user","text":user_message})

        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system=BUSINESS_INFO,
                messages=[{"role":m["role"] if m["role"] =="user" else "assistant",
                          "content":m["text"]} for m in conversation]
            )



            ai_reply = message.content[0].text
            conversation.append({"role": "ai","text":ai_reply})


        except Exception as e:
            conversation.pop()
            print("API error",e)

        return redirect(url_for("index"))
    return render_template_string(HTML,history=conversation)





@app.route("/reset")
def reset():
    conversation.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True,port=5001)
