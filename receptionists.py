from flask import Flask, render_template_string, request, redirect , url_for , session
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
from functools import wraps
DASHBOARD_USER=os.getenv('DASHBOARD_USER')
DASHBOARD_PASSWORD=os.getenv("DASHBOARD_PASSWORD")
from google.oauth2 import  service_account
from googleapiclient.discovery import build
from datetime import datetime






app = Flask(__name__)
app.secret_key="Arsenal_fc"
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
- Once you have all the details, tell them their request has been received and the clinic will follow up shortly to confirm the appointment.
- Never tell them the appointment is booked or confirmed. You cannot see the appointment book, so you cannot promise a slot.
- Only book service we offer: check-ups, nonsense, or rude messages. Don't play along with the pranks; steer back to helping with a dental
  appointment.
- When confirming the booking details back to the customer, state the actual calendar date (for example "Monday, August 4th"), not just the relative day like "next Monday", so there is no confusion about which date they mean.
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
  h1 { color: #0f7d8c; }
  table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }
  th { background: #0f7d8c; color: white; padding: 12px; text-align: left; font-size: 14px; }
  td { padding: 12px; border-bottom: 1px solid #eee; font-size: 14px; }
  .new { color: #e67e22; font-weight: bold; }
  .confirmed { color: #27ae60; font-weight: bold; }
  .cancelled { color: #c0392b; font-weight: bold; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .badge.new { background: #fdf1e0; color: #b26a00; }
  .badge.confirmed { background: #e6f4ec; color: #1f7a45; }
  .badge.cancelled { background: #eef1f2; color: #8a939a; }
  .empty { background: white; padding: 40px; text-align: center; color: #888; border-radius: 8px; }
  button { border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; color: white; font-size: 13px; }
  .ok { background: #27ae60; }
  .no { background: #c0392b; }
  .clash { background: #fcecea; color: #c0392b; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; }
  
  
  .filters { margin-bottom: 15px; }
  .filters a { display: inline-block; padding: 8px 16px; margin-right: 6px; background: white; color: #0f7d8c; text-decoration: none; border-radius: 999px; font-size: 14px; 1px solid #e3e9ec; }
  .filters a.active { background: #0f7d8c; color: white; }
  
  .stats { display: flex; gap: 12px; margin-bottom: 20px; }
  .stat { flex: 1; background: white; border-radius: 8px; padding: 16px; }
  .stat .n { font-size: 28px; font-weight: bold; color: #0f7d8c; }
  .stat .l { font-size: 12px; color: #888; margin-top: 4px; text-transform: uppercase; }
  .stat.new .n { color: #e67e22; }
  .stat.confirmed .n { color: #27ae60; }
  .stat.cancelled .n { color: #c0392b; }
  .day-header td { background: #eef2f4; color: #0f7d8c; font-weight: bold; font-size: 15px; padding: 14px 12px; border-top: 2px solid #0f7d8c; }
  
</style>
</head>
<body>

<h1>Bookings</h1>
<div class="stats">
  <div class="stat total"><div class="n">{{ total }}</div><div class="l">Total</div></div>
  <div class="stat new"><div class="n">{{ new_count }}</div><div class="l">New</div></div>
  <div class="stat confirmed"><div class="n">{{ confirmed_count }}</div><div class="l">Confirmed</div></div>
  <div class="stat cancelled"><div class="n">{{ cancelled_count }}</div><div class="l">Cancelled</div></div>
</div>
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
    <th>Phone</th><th>Email</th><th>Service</th><th>Status</th><th>Slot</th><th>Actions</th>
  </tr>
  
  {% for day, day_bookings in grouped.items() %}
  
  <tr class="day-header"><td colspan="10">{{ day }} — {{ day_bookings|length }} requests · {{ day_bookings|selectattr("status", "equalto", "new")|list|length }} new</td></tr>
  {% for b in day_bookings %}
  <tr>
    <td>{{ b["timestamp"] }}</td>
    <td>{{ b["name"] }}</td>
    <td>{{ b["day"] }}</td>
    <td>{{ b["time"] }}</td>
    <td>{{ b["phone"] }}</td>
    <td>{{ b["email"] }}</td>
    <td>{{ b["service"] }}</td>
    
    <td><span class="badge {{ b['status'] }}">{{ b["status"] }}</span></td>
    <td>{% if b["slot_note"] == "CLASH" %}<span class="clash">⚠ CLASH</span>{% endif %}</td>
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
  {% endfor %}
</table>
{% else %}
<div class="empty">No bookings yet.</div>
{% endif %}
</body>
</html>
"""

conversation=[]
conversations={}
booking_done = False
def check_auth(username, password):
    return username == DASHBOARD_USER and password == DASHBOARD_PASSWORD

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return ("Access denied", 401,
                    {"WWW-Authenticate":'Basic realm="Bookings"'})
        return f(*args, **kwargs)
    return wrapper

def is_slot_taken(date,time):
    if not date or not time:
        return False
    conn=sqlite3.connect("bookings.db")
    count = conn.execute("SELECT COUNT(*) FROM bookings WHERE date=? AND time=? AND status != 'cancelled'",
                         (date,time)
                         ).fetchone()[0]
    conn.close()
    return count > 0







@app.route("/bookings")
@require_auth
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
    grouped ={}
    for b in rows:
        if b["date"]:
            key = datetime.strptime(b["date"],"%Y-%m-%d").strftime("%A, %b %d")
        else:
            key = "No date"

        if key not in grouped:
            grouped[key] = []
        grouped[key].append(b)
    grouped = dict(sorted(grouped.items()))

    all_statuses = conn.execute("SELECT * FROM bookings").fetchall()
    total = len(all_statuses)
    new_count = sum(1 for r in all_statuses if r["status"] == "new")
    confirmed_count = sum(1 for r in all_statuses if r["status"] == "confirmed")
    cancelled_count = sum(1 for r in all_statuses if r["status"] == "cancelled")

    conn.close()
    return render_template_string(BOOKINGS_HTML, bookings= rows, current= status_filter,
                                  total=total,new_count=new_count,confirmed_count=confirmed_count,cancelled_count=cancelled_count,
                                  grouped=grouped,
                                  )


@app.route("/bookings/<int:bookings_id>/<status>",methods=["POST"])
@require_auth
def booking(bookings_id,status):
    if status not in ("confirmed","cancelled"):
        return redirect(url_for("bookings"))
    conn = sqlite3.connect("bookings.db")
    conn.row_factory= sqlite3.Row
    conn.execute("UPDATE bookings SET status=? WHERE id=?",(status,bookings_id))
    conn.commit()
    row = conn.execute("SELECT * FROM bookings WHERE id=?",(bookings_id,)).fetchone()


    conn.close()
    if row:
        send_status_email(dict(row),status)
        if status == "confirmed":
            add_to_calendar(dict(row))

    return redirect(url_for("bookings"))

    
@app.route("/",methods=["GET","POST"])

def index():
    if "booking_done" not in session:
        session["booking_done"] = False

    if "conversation" not in session:
        session["conversation"] = []
    if request.method == "POST":
        user_message = request.form.get("message","").strip()

        if not user_message:
            return redirect(url_for("index"))
        session["conversation"].append({"role":"user","text":user_message})

        try:
            today = datetime.now().strftime("%A,%Y-%m,%d")
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system= f"Today is {today}.\n\n" + BUSINESS_INFO,
                messages=[{"role":m["role"] if m["role"] =="user" else "assistant",
                          "content":m["text"]} for m in session["conversation"]]
            )



            ai_reply = message.content[0].text
            session["conversation"].append({"role": "ai","text":ai_reply})

            if not session["booking_done"]:
                booking= extract_booking(session["conversation"])

                if booking and booking.get("complete"):
                    session["booking_done"]= True

                    save_booking(booking)
                    send_confirmation(booking)
                    
                    print("Booking saved:",booking)





        except Exception as e:
            session["conversation"].pop()
            print("API error",e)



    session.modified = True
    return render_template_string(HTML,history=session["conversation"])

@app.route("/voice",methods=["POST"])
def voice():
    caller_number = request.form.get("From","unknown")
    conversations[caller_number]=[]
    response = VoiceResponse()
    gather = Gather(input="speech",action="/respond",method="POST",speech_timeout="auto")
    gather.say("Thank you for calling Smile Dental Clinic.How can I help you today?")
    response.append(gather)
    return str(response)

@app.route("/respond",methods=["POST"])
def respond():
    caller_speech = request.form.get("SpeechResult", "").strip()
    caller_number = request.form.get("From","unknown")

    response = VoiceResponse()

    if not caller_speech:
        response.say("Sorry, I don't understand you. Goodbye.")
        response.hangup()
        return str(response)
    if caller_number not in conversations:
        conversations[caller_number] = []
    conversation = conversations[caller_number]

    conversation.append({"role":"user","text":caller_speech})

    try:
        today = datetime.now().strftime("%A, %Y-%m-%d")
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=f"Today is {today}.\n\n" + VOICE_INFO,
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


def extract_booking(conversation):
    today = datetime.now().strftime("%A,%Y-%m-%d")

    extract_prompt =f""" Today is {today}. Read the conversation and extract the booking details.
    
    
    Return ONLY a raw JSON object, no markdown, no code fences, in exactly this format:
    {{"name":"","day":"","time":"","date":"",phone":"","email":"","service":"","complete":false}}
    
    
    Rules:
    - Extract EVERY field the customer has provided anywhere in the conversation, even if given all at once or out of order.
    - phone: keep only the digits the customer gave,as a string.
    - service: if they mention more than one service,join them(e.g. "Filling and Whitening").
    - email: capture any email address mentioned anywhere in the conversation.
    - Set "complete" to true ONLY if name, day , time, and phone are all present.
    - Leave any missing field as an empty string.
    - Only set "complete" true for a genuine request for a service this clinic offers(check-ups,cleaning,fillings,whitening).If the service is unrelated, nonsensical, or 
      no a real dental booking, leave "complete" false and "service"empty.
    - date: work out the actual calendar date from today's date above , as YYYY_MM_DD.
    -Always format "time" in 12-hour format with AM/PM or "4:30 PM". Always include minutes(":00 if none given) and a space before AM/PM ,midnight is "12:00 AM".
    
    
    
    
    """




    

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

def send_status_email(booking,status):
    if not booking.get("email"):
        return
    msg = EmailMessage()
    msg["From"]= GMAIL_ADDRESS
    msg["TO"]=booking["email"]

    if status == "confirmed":
        msg["subject"]="Your appointment is confirmed -Smile Dental Clinic"
        msg.set_content(
            f"""HI {booking['name']},
            Your appointment is now confirmed:
            Day: {booking['day']}
            Time: {booking['time']}
            service: {booking['service']}
            
    We'll see you at 123 Main Street,Toronto.
    
    Smile Dental Clinic"""
        )
    else:
        msg["Subject"] = "About your appointment - Smile Dental Clinic"
        msg.set_content(
            f""" Hi {booking['name']}'
    Unfortunately, we can't offer the slot you requested for {booking['day']} at {booking['time']}.
    Please call us to arrange another time.
    Smile Dental  Clinic"""
        )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as smtp:
            smtp.login(GMAIL_ADDRESS,GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print(f"Status email {status} sent to ",booking["email"])
    except Exception as e:
        print("Email could not be sent:",e)


def add_to_calendar(booking):
    try:
        creds = service_account.Credentials.from_service_account_file(
            "calendar-key.json",
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        service = build("calendar", "v3", credentials=creds)
        summary =f"{booking['service']} -{booking['name']}"
        description = (
            f"Phone:{booking['phone']}\n"
            f"Email:{booking['email']}\n"
            f"Requested day:{booking['day']}"
            f"Requested time:{booking['time']}"

        )
        event_date =  booking.get("date") or datetime.now().strftime("%Y-%m-%d")


        event = {
            "summary": summary,
            "description": description,
            "start":{"date": event_date },
            "end":{"date": event_date },
        }
        service.events().insert(calendarId=GMAIL_ADDRESS,body=event).execute()
        print("Added to calendar:",summary)
    except Exception as e:
        print("Calendar add failed:",e)




            


def init_db():
    conn = sqlite3.connect("bookings.db")
    conn.execute("""
     CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp  TEXT,
        name TEXT,
        time TEXT,
        date TEXT,
        day TEXT,
        phone TEXT,
        email TEXT,
        service TEXT,
        slot_note TEXT,
        status TEXT DEFAULT 'new'
    )
    
    
    
    
    
    
    





""")
    conn.commit()
    conn.close()










    
    
    
def save_booking(booking):

    booking["timestamp"]=datetime.now().strftime("%Y-%m-%d %H:%M")
    if is_slot_taken(booking.get("date",""),booking.get("time","")):
        booking["slot_note"]="CLASH"
    else:
        booking["slot_note"]=""
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
    INSERT INTO bookings(timestamp,name,day,time,date,phone,email,service, slot_note)
    VALUES (?,?,?,?,?,?,?,?,?)
    
    
    
    """,(

    booking.get("timestamp",""),
    booking.get("name",""),
    booking.get("day",""),
    booking.get("time",""),
    booking.get("date",""),
    booking.get("phone",""),
    booking.get("email",""),
    booking.get("service",""),
    booking.get("slot_note","")
    ))
    conn.commit()
    conn.close()


















@app.route("/reset")
def reset():
    global booking_done
    session["conversation"] =[]


    booking_done = False
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True,port=5001)
