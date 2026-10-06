"""Twelve tasks with exact answers, in three tiers. Answers that need arithmetic are computed, not typed."""

from math import lcm

EASY = [
    ("Classify this support ticket as billing, bug, account, feature_request or security. Reply with the label only.\n"
     "Ticket: I was charged twice for September.", "billing"),
    ("Is this message positive or negative? Reply with one word.\nMessage: The export finally works, thank you!",
     "positive"),
    ("Extract the invoice number from: 'Please check INV-20931, the total looks wrong.' Reply with the number only.",
     "INV-20931"),
    ("What is the domain of the email address ops@riversidelegal.example? Reply with the domain only.",
     "riversidelegal.example"),
]

MEDIUM = [
    ("Convert 'the 3rd of March, 2026' to ISO format (YYYY-MM-DD). Reply with the date only.", "2026-03-03"),
    ("How many distinct people are mentioned? 'Ana emailed Marco and Priya; Marco replied to Ana and copied Dev.' "
     "Reply with a number only.", "4"),
    ("A plan costs $49 per month. What is the total for 7 months, in dollars? Reply with a number only.", str(49 * 7)),
    ("Sort INV-88, INV-9 and INV-120 by their numbers and give the middle one. Reply with the ID only.", "INV-88"),
]

HARD = [
    ("A customer is on Starter ($12 per 30-day period) for days 1-10 and on Team ($49 per 30-day period) for days "
     "11-30 of one period, billed pro rata by day. What do they owe for the period, in dollars, rounded to 2 decimal "
     "places? Reply with the number only.", f"{10 / 30 * 12 + 20 / 30 * 49:.2f}"),
    ("Server A fails every 6 days, B every 10 days and C every 15 days. All three failed on day 0. On what day do all "
     "three next fail on the same day? Reply with the day number only.", str(lcm(6, 10, 15))),
    ("API pricing: the first 1,000 calls are free, the next 9,000 cost $0.002 each, and every call beyond 10,000 costs "
     "$0.001. What do 25,000 calls cost, in dollars? Reply with the number only.",
     f"{9000 * 0.002 + 15000 * 0.001:g}"),
    ("Ana is free 09:00-12:00 and 14:00-17:00. Marco is free 10:00-13:00 and 15:00-18:00. Priya is free "
     "11:00-16:00. What is the earliest start time of a 1-hour meeting all three can attend? Reply as HH:MM only.",
     "11:00"),
]

TASKS = [("easy", q, a) for q, a in EASY] + [("medium", q, a) for q, a in MEDIUM] + [("hard", q, a) for q, a in HARD]
