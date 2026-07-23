from flask import Flask, render_template_string, request, redirect , url_for
import anthropic
import os
from dotenv import load_dotenv
load_dotenv()
import csv
import json
from datetime import datetime
import smtplib
from email.message import EmailMessage

from twilio.twiml.voice_response import VoiceResponse, Gather
import sqlite3



app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
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
- If someone wants to book, ask for their name, preferred day,  phone number, and email address for confirmation
-Once you have all the details,let them know their request has been received and a confirmation email will be sent
- Keep replies short and warm, like a real receptionist on the phone
"""




VOICE_INFO = BUSINESS_INFO +"""

This is a phone call, not a text chat, not a text chat.
-Speak in plain sentences only.No markdown, no asterisks, no bullet points, no numbered lists, no emoji.
-keep every reply to one or two sentences.
-Read phone numbers and emails back slowly to confirm you heard them correctly.






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
<form method="POST" onsubmit="this.querySelector('button').disabled=true">
  <input type="text" name="message" placeholder="Type your message..." autofocus>
  <button type="submit">Send</button>
</form>
</body>
</html>
"""
BOOKINGS_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Bookings - Smile Dental</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 1000px; margin: 40px auto; background: #f5f5f5; padding: 20px; }
  h1 { color: #2c3e50; }
  table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }
  th { background: #2c3e50; color: white; padding: 12px; text-align: left; font-size: 14px; }
  td { padding: 12px; border-bottom: 1px solid #eee; font-size: 14px; }
  .new { color: #e67e22; font-weight: bold; }
  .confirmed { color: #27ae60; font-weight: bold; }
  .cancelled { color: #c0392b; font-weight: bold; }
  .empty { background: white; padding: 40px; text-align: center; color: #888; border-radius: 8px; }
  button { border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; color: white; font-size: 13px; }
  .ok { background: #27ae60; }
  .no { background: #c0392b; }
  .filters { margin-bottom: 15px; }
  .filters a { display: inline-block; padding: 8px 16px; margin-right: 6px; background: white; color: #2c3e50; text-decoration: none; border-radius: 6px; font-size: 14px; }
  .filters a.active { background: #2c3e50; color: white; }
</style>
</head>
<body>

<h1>Bookings</h1>
<div class="filters">
  <a href="/bookings" class="{{ 'active' if current == 'all' }}">All</a>
  <a href="/bookings?status=new" class="{{ 'active' if current == 'new' }}">New</a>
  <a href="/bookings?status=confirmed" class="{{ 'active' if current == 'confirmed' }}">Confirmed</a>
  <a href="/bookings?status=cancelled" class="{{ 'active' if current == 'cancelled' }}">Cancelled</a>
</div>
{% if bookings %}
<table>
  <tr>
    <th>Received</th><th>Name</th><th>Day</th><th>Time</th>
    <th>Phone</th><th>Email</th><th>Service</th><th>Status</th><th>Actions</th>
  </tr>
  {% for b in bookings %}
  <tr>
    <td>{{ b["timestamp"] }}</td>
    <td>{{ b["name"] }}</td>
    <td>{{ b["day"] }}</td>
    <td>{{ b["time"] }}</td>
    <td>{{ b["phone"] }}</td>
    <td>{{ b["email"] }}</td>
    <td>{{ b["service"] }}</td>
    <td class="{{ b['status'] }}">{{ b["status"] }}</td>
    <td>
      <form method="POST" action="/bookings/{{ b['id'] }}/confirmed" style="display:inline">
        <button class="ok">Confirm</button>
      </form>
      <form method="POST" action="/bookings/{{ b['id'] }}/cancelled" style="display:inline">
        <button class="no">Cancel</button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% else %}
<div class="empty">No bookings yet.</div>
{% endif %}
</body>
</html>
"""

conversation=[]
booking_done = False

@app.route("/bookings")
def bookings():
    status_filter = request.args.get("status","all")
    conn = sqlite3.connect("bookings.db")
    conn.row_factory = sqlite3.Row
    if status_filter in ("new","confirmed","cancelled"):
        rows = conn.execute("SELECT * FROM bookings WHERE status = ? ORDER BY  id DESC",
        (status_filter,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM bookings ORDER BY id DESC").fetchall()
    conn.close()
    return render_template_string(BOOKINGS_HTML, bookings= rows, current= status_filter)

@app.route("/bookings/<int:bookings_id>/<status>",methods=["POST"])
def booking(bookings_id,status):
    if status not in ("confirmed","cancelled"):
        return redirect(url_for("bookings"))
    conn = sqlite3.connect("bookings.db")
    conn.execute("UPDATE bookings SET status=? WHERE id=?",(status,bookings_id))
    conn.commit()
    conn.close()
    return redirect(url_for("bookings"))

    
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
            global booking_done
            if not booking_done:
                booking= extract_booking()
                if booking and booking.get("complete"):
                    booking_done = True

                    save_booking(booking)
                    send_confirmation(booking)
                    
                    print("Booking saved:",booking)





        except Exception as e:
            conversation.pop()
            print("API error",e)

        return redirect(url_for("index"))
    return render_template_string(HTML,history=conversation)

@app.route("/voice",methods=["POST"])
def voice():
    response = VoiceResponse()
    gather = Gather(input="speech",action="/respond",method="POST",speech_timeout="auto")
    gather.say("Thank you for calling Smile Dental Clinic.How can I help you today?")
    response.append(gather)
    return str(response)

@app.route("/respond",methods=["POST"])
def respond():
    caller_speech = request.form.get("SpeechResult", "").strip()

    response = VoiceResponse()

    if not caller_speech:
        response.say("Sorry, I don't understand you. Goodbye.")
        response.hangup()
        return str(response)

    conversation.append({"role":"user","text":caller_speech})

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=VOICE_INFO,
            messages=[{"role":m["role"] if m["role"] =="user" else "assistant",
                     "content": m["text"]} for m in conversation]


        )
        ai_reply = message.content[0].text
        conversation.append({"role":"ai","text":ai_reply})
    except Exception as e:
        conversation.pop()
        print("API error",e)
        ai_reply="Sorry,something went wrong.Please try again later."
    gather = Gather(input="speech",action="/respond",method="POST",speech_timeout="auto")
    gather.say(ai_reply)
    response.append(gather)
    return str(response)


def extract_booking():
    extract_prompt="""Read the conversation and extract the booking details.
    Return ONLY a JSON object,no other text, in exactly this format:
    {"name":"","day": "","time": "","phone":"","email":"","service":"","complete":false}
    Set "complete" to true ONLY if name,day,time and phone are all present.
    Leave any missing field as an empty string."""

    result = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=extract_prompt,

        messages=[{"role": "user",
        "content":"Here is the conversation:\n\n"+
        "\n".join(f'{m["role"]}:{m["text"]}' for m in conversation)}]

    )

    raw = result.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:

        return json.loads(raw)
    except json.JSONDecodeError:
        print("Could not parse JSON:",raw)
        return None

def send_confirmation(booking):
    if not booking.get("email"):
        return
    msg = EmailMessage()
    msg["Subject"]="Your appointment at Smile Dental Clinic"
    msg["From"]= GMAIL_ADDRESS
    msg["To"]= booking["email"]
    msg.set_content(
        f""" Hi {booking["name"]},
        
    Your appointment request has been received:
    
    Day: {booking["day"]}
    Time: {booking["time"]}
    service: {booking["service"]}
    
    We'll see you at 123 Main Street,Toronto.
    
    Smile Dental  Clinic"""
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS,GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print("Confirmation email sent to ",booking["email"])
    except Exception as e:
        print("Email could not be sent:",e)


def init_db():
    conn = sqlite3.connect("bookings.db")
    conn.execute("""
     CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp  TEXT,
        name TEXT,
        time TEXT,
        day TEXT,
        phone TEXT,
        email TEXT,
        service TEXT,
        status TEXT DEFAULT 'new'
    )
    
    
    
    
    
    
    





""")
    conn.commit()
    conn.close()










    
    
    
def save_booking(booking):
    booking["timestamp"]=datetime.now().strftime("%Y-%m-%d %H:%M")
    fields=["timestamp","name","day","time","phone","email","service"]
    file_exists= os.path.exists("bookings.csv")

    with open("bookings.csv","a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        writer.writerow({key:booking.get(key,"") for key in fields
                         })

    conn = sqlite3.connect("bookings.db")
    conn.execute("""
    INSERT INTO bookings(timestamp,name,day,time,phone,email,service)
    VALUES (?,?,?,?,?,?,?)
    
    
    
    """,(

    booking.get("timestamp",""),
    booking.get("name",""),
    booking.get("day",""),
    booking.get("time",""),
    booking.get("phone",""),
    booking.get("email",""),
    booking.get("service","")
    ))
    conn.commit()
    conn.close()


















@app.route("/reset")
def reset():
    global booking_done

    conversation.clear()
    booking_done = False
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True,port=5001)
