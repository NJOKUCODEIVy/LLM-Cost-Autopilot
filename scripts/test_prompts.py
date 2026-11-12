"""
Ten baseline test prompts for the LLM Cost Autopilot, three to four per tier.

Tier 1 = simple (reformatting, extraction, Q&A from provided text)
Tier 2 = moderate (summarizing, classifying, structured output)
Tier 3 = complex (multi-step reasoning, comparisons, creative writing, judgment)
"""

TEST_PROMPTS = [
    # --- Tier 1: simple ---
    {
        "id": 1,
        "tier": 1,
        "prompt": "Convert this date to YYYY-MM-DD format. Reply with the date only: March 7th, 2025",
    },
    {
        "id": 2,
        "tier": 1,
        "prompt": (
            "Extract the email address from this text. Reply with the email only: "
            "'For support, contact Dana at dana.reyes@brightpath.io or call extension 4410.'"
        ),
    },
    {
        "id": 3,
        "tier": 1,
        "prompt": (
            "Based only on this text, what year was the company founded? Reply with the year only. "
            "Text: 'Lumen Bakery opened its first shop in Leeds in 1998 and now has 12 locations.'"
        ),
    },
    # --- Tier 2: moderate ---
    {
        "id": 4,
        "tier": 2,
        "prompt": (
            "Summarize this in two sentences: 'The city library system will extend weekday hours "
            "to 9 p.m. starting in April, after a survey in which 62% of residents said evening "
            "access was their top request. The change will be funded by moving part of the budget "
            "previously spent on printed magazines, most of which are now available digitally. "
            "Weekend hours will stay the same, and the three smallest branches will keep their "
            "current schedule until staffing improves.'"
        ),
    },
    {
        "id": 5,
        "tier": 2,
        "prompt": (
            "Classify the sentiment of this review as positive, negative, or mixed. "
            "Reply with one word: 'The battery lasts all day and the screen is gorgeous, "
            "but the speakers crackle at high volume and support took a week to reply.'"
        ),
    },
    {
        "id": 6,
        "tier": 2,
        "prompt": (
            "Convert this sentence to JSON with the fields name, role, and start_date "
            "(start_date in YYYY-MM-DD format). Reply with the JSON only: "
            "'Priya Nair joins as a Data Analyst on 3 February 2026.'"
        ),
    },
    # --- Tier 3: complex ---
    {
        "id": 7,
        "tier": 3,
        "prompt": (
            "A train leaves at 9:40 a.m. and travels 210 km at 84 km/h. It then waits 25 minutes, "
            "and travels another 96 km at 64 km/h. What time does it arrive? "
            "Show your reasoning briefly, then give the final time."
        ),
    },
    {
        "id": 8,
        "tier": 3,
        "prompt": (
            "A 5-person startup must choose between a monolith and microservices for its first "
            "product. Compare the two on development speed, cost, and risk, then recommend one. "
            "Keep it under 150 words."
        ),
    },
    {
        "id": 9,
        "tier": 3,
        "prompt": (
            "Write a four-line poem about a lighthouse keeper's last night on the job. "
            "Use an ABAB rhyme scheme."
        ),
    },
    {
        "id": 10,
        "tier": 3,
        "prompt": (
            "An engineer found a bug that exposes customer email addresses. Fixing it will delay "
            "a launch promised to a major client by two weeks. List the key considerations and "
            "recommend what the team should do. Keep it under 150 words."
        ),
    },
]