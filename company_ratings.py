import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

KNOWN_RATINGS = {
    "google":       {"rating": 4.5, "review": "Excellent",  "environment": "World class work culture"},
    "microsoft":    {"rating": 4.4, "review": "Excellent",  "environment": "Great WLB, good benefits"},
    "amazon":       {"rating": 3.8, "review": "Good",       "environment": "Fast paced, high pressure"},
    "infosys":      {"rating": 3.6, "review": "Good",       "environment": "Good for freshers, learning culture"},
    "tcs":          {"rating": 3.5, "review": "Average",    "environment": "Stable job, slow growth"},
    "wipro":        {"rating": 3.4, "review": "Average",    "environment": "Decent for freshers"},
    "cognizant":    {"rating": 3.5, "review": "Average",    "environment": "Good projects, avg pay"},
    "accenture":    {"rating": 3.7, "review": "Good",       "environment": "Good learning, global exposure"},
    "flipkart":     {"rating": 4.1, "review": "Very Good",  "environment": "Startup energy, good pay"},
    "swiggy":       {"rating": 3.9, "review": "Good",       "environment": "Fast growth, good culture"},
    "zomato":       {"rating": 3.8, "review": "Good",       "environment": "Young team, good perks"},
    "paytm":        {"rating": 3.5, "review": "Average",    "environment": "Unstable recently"},
    "zoho":         {"rating": 4.0, "review": "Very Good",  "environment": "Great for freshers, good WLB"},
    "persistent":   {"rating": 3.8, "review": "Good",       "environment": "Good tech exposure"},
    "thoughtworks": {"rating": 4.2, "review": "Very Good",  "environment": "Excellent tech culture"},
    "esparkbiz":    {"rating": 4.1, "review": "Very Good",  "environment": "Good for freshers, Gujarat based"},
    "tatvasoft":    {"rating": 4.0, "review": "Very Good",  "environment": "Good work culture, Ahmedabad"},
    "bacancy":      {"rating": 3.9, "review": "Good",       "environment": "Good projects, remote friendly"},
    "adobe":        {"rating": 4.3, "review": "Excellent",  "environment": "Creative culture, great pay"},
    "jp morgan":    {"rating": 4.1, "review": "Very Good",  "environment": "Great for finance tech"},
    "goldman sachs":{"rating": 4.2, "review": "Very Good",  "environment": "High pay, high pressure"},
    "hcl":          {"rating": 3.4, "review": "Average",    "environment": "Stable, slow growth"},
    "tech mahindra":{"rating": 3.3, "review": "Average",    "environment": "Decent, avg pay"},
    "capgemini":    {"rating": 3.6, "review": "Good",       "environment": "Good work life balance"},
    "byju":         {"rating": 2.8, "review": "Poor",       "environment": "Unstable, payment issues"},
    "unacademy":    {"rating": 3.2, "review": "Average",    "environment": "Layoffs recently"},
    "isro":         {"rating": 4.8, "review": "Excellent",  "environment": "Prestigious, job security, great research"},
    "drdo":         {"rating": 4.7, "review": "Excellent",  "environment": "Govt job security, research focused"},
    "barc":         {"rating": 4.6, "review": "Excellent",  "environment": "Top research institute, excellent benefits"},
}

def get_star_rating(rating):
    full = int(rating)
    half = 1 if (rating - full) >= 0.5 else 0
    empty = 5 - full - half
    return ("*" * full) + ("~" * half) + ("-" * empty) + f" {rating}/5"

def get_company_rating(company_name):
    company_lower = company_name.lower().strip()
    for key, data in KNOWN_RATINGS.items():
        if key in company_lower or company_lower in key:
            return {
                "rating": data["rating"],
                "stars": get_star_rating(data["rating"]),
                "review": data["review"],
                "environment": data["environment"],
            }
    return {
        "rating": 0,
        "stars": "Not rated",
        "review": "Check Glassdoor",
        "environment": "Check reviews online",
    }
