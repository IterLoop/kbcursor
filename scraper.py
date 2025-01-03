import os
from apify_client import ApifyClient
from config import APIFY_API_KEY
# Initialize the ApifyClient with your API token
# Get API token from environment variable or set it here
API_TOKEN = "apify_api_RqJ95dSauHAkMv1WGiajI2ysI8zAlg04FzoV"


# Read search terms from file
def read_search_terms(filename='searchlist.txt'):
    if not os.path.exists(filename):
        print(f"Error: {filename} not found")
        return []
        
    with open(filename, 'r') as f:
        # Read lines and remove whitespace
        terms = [line.strip() for line in f.readlines()]
        # Remove empty lines
        terms = [term for term in terms if term]
    return terms

# Initialize the ApifyClient with your API token
client = ApifyClient(API_TOKEN)

# Get search terms
search_terms = read_search_terms()
if not search_terms:
    print("No search terms found. Please add terms to searchlist.txt")
    exit(1)

# Convert list to newline-separated string
queries = "\n".join(search_terms)

# Prepare the Actor input
run_input = {
    "queries": queries,
    "resultsPerPage": 1,
    "maxPagesPerQuery": 1,
    "languageCode": "",
    "forceExactMatch": False,
    "wordsInTitle": [],
    "wordsInText": [],
    "wordsInUrl": [],
    "mobileResults": False,
    "includeUnfilteredResults": False,
    "saveHtml": False,
    "saveHtmlToKeyValueStore": True,
    "includeIcons": False,
}

# Run the Actor and wait for it to finish
run = client.actor("nFJndFXA5zjCTuudP").call(run_input=run_input)

# Fetch and print Actor results from the run's dataset
print("\nSearch Results:")
print("-" * 50)
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(item)
    print("-" * 50)
