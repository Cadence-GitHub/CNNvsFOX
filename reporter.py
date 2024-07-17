import dotenv, os
import requests
import re
from datetime import datetime
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import anthropic
import json


dotenv.load_dotenv()

client_anthropic = anthropic.Anthropic()


def load_excluded_articles():
    try:
        with open("excluded_articles", "r") as file:
            return set(line.strip() for line in file)
    except FileNotFoundError:
        return set()

def get_cnn_articles():
    excluded_urls = load_excluded_articles()
    r = requests.get('https://lite.cnn.com/')
    soup = BeautifulSoup(r.content, 'html.parser')
    items = soup.find('ul').find_all('li')
   
    cnn_articles = []
    for item in items:
        link = f"https://lite.cnn.com{item.find('a')['href']}"
        if link not in excluded_urls:
            title = item.find('a').text.strip()
            cnn_articles.append(f"CNN Title: {title}\nLink: {link}\n")
   
    return "\n".join(cnn_articles)

def get_fox_news_articles():
    excluded_urls = load_excluded_articles()
    r = requests.get('https://moxie.foxnews.com/google-publisher/latest.xml')
    root = ET.fromstring(r.content)
    items = root.findall('.//item')
   
    fox_articles = []
    for item in items:
        link = item.find('link').text
        if link not in excluded_urls:
            title = item.find('title').text
            fox_articles.append(f"FOX Title: {title}\nLink: {link}\n")
   
    return "\n".join(fox_articles)

# Get and store CNN articles
cnn_content = get_cnn_articles()

# Get and store Fox News articles
fox_news_content = get_fox_news_articles()

# Print the results
print("CNN Articles:")
print(cnn_content)
print("\nFox News Articles:")
print(fox_news_content)




def answer_question(cnn_content, fox_news_content):
    answer = client_anthropic.messages.create(
        model="claude-3-5-sonnet-20240620",
        #model="claude-3-opus-20240229",
        #model="claude-3-haiku-20240307",
        max_tokens=2000,
        temperature=0,
        system="You are an expert at reading news, analyzing them, and answering questions about them. \
You will receive a list of recent articles published on CNN and Fox News websites. \
The list of CNN articles is provided within the <CNN_articles></CNN_articles> tag. \
The list of Fox News articles is provided within the <FOX_articles></FOX_articles> tag. \
Read the lists of these articles carefully and remember them all because I will give you an important task related to these lists.",

        messages=[
            {
                "role": "user",
                "content": [
                {
                    "type": "text",
                    "text": f"<CNN_articles>\n{cnn_content}\n</CNN_articles>\n\n\n <FOX_articles>\n{fox_news_content}\n</FOX_articles>\n\n\n \
By comparing article titles, find a pair of corresponding articles on CNN and FOX News that describe the same event or news. \
You might notice many potential pairs like that, but only output one pair that you are most certain is on the exact same topic. \
Your output needs to absolutely meet all the following requirements: \
* You need to be 100 percent sure that EXACTLY the same topic is discussed, not just sounding similar. \
* You need to be 100 percent sure that one of the articles is from CNN and the other one is from FOX News. \
* You cannot give a pair of articles where both articles are from CNN, and you cannot give a pair where both articles are from FOX. \
* Do not give pairs of articles where one of the articles seem to expand or cover more topics than the other one. \
* If you cannot find a matching pair of articles where you are 100 percent sure they are about exactly the same topic, just say that you cannot find it, don't try to make up an answer. \
It's perfectly fine if you cannot find a matching pair of articles. \
\nBefore providing the pair of articles, please think about it step-by-step within <thinking></thinking> tags. Then, provide your final answer within <answer></answer> tags. \
Provide the complete links to the selected articles in the <link_to_cnn_article></link_to_cnn_article> and <link_to_fox_article></link_to_fox_article> tags. \
Provide the full titles of the selected articles in the <title_of_cnn_article></title_of_cnn_article> and <title_of_fox_article></title_of_fox_article> tags.",
                }
            ]
            }
        ]
    )
    # print (answer)
    return answer.content[0].text




LLM_answer_pair = answer_question(cnn_content, fox_news_content)
print (LLM_answer_pair)



def extract_text_from_tags(LLM_answer, tag_name):
    pattern = f'<{tag_name}>(.*?)</{tag_name}>'
    match = re.search(pattern, LLM_answer, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        print(f"No match found for {tag_name}.")
        exit(1)

def save_links_to_file(links):
    try:
        with open("excluded_articles", "a") as file:
            for link in links:
                if link.startswith('http'):
                    file.write(f"{link}\n")
        print("Links successfully written to file.")
    except IOError as e:
        print(f"An error occurred while writing to the file: {e}")

# Usage
link_to_cnn_article = extract_text_from_tags(LLM_answer_pair, 'link_to_cnn_article')
link_to_fox_article = extract_text_from_tags(LLM_answer_pair, 'link_to_fox_article')
title_of_cnn_article = extract_text_from_tags(LLM_answer_pair, 'title_of_cnn_article')
title_of_fox_article = extract_text_from_tags(LLM_answer_pair, 'title_of_fox_article')


print(f"CNN title: {title_of_cnn_article}")
print(f"CNN link: {link_to_cnn_article}\n")
print(f"Fox title: {title_of_fox_article}")
print(f"Fox link: {link_to_fox_article}")


def normalize_quotes(text):
    """
    Normalize various types of quotes and apostrophes to standard ASCII versions.
    """
    replacements = {
        '‘': "'",  # Right single quotation mark
        '’': "'",  # Left single quotation mark
        '“': '"',  # Left double quotation mark
        '”': '"',  # Right double quotation mark
        '′': "'",  # Prime
        '‚': "'",  # Single low-9 quotation mark
        '‛': "'",  # Single high-reversed-9 quotation mark
        '„': '"',  # Double low-9 quotation mark
        '⹂': '"',  # Double low-9 reversed quotation mark
        '‟': '"',  # Double high-reversed-9 quotation mark
        '`': "'",  # Grave accent
        '´': "'",  # Acute accent
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text

def verify_article_existence(article, list_of_articles):    
    normalized_article = normalize_quotes(article.strip())
    normalized_list = normalize_quotes(list_of_articles)
    
    if normalized_article in normalized_list:
        return True
    
    else:
        print(f"The following text could not be found in the list of articles: {normalized_article}")
        print(f"List of articles: \n {normalized_list}")
        return False
    

if not (verify_article_existence(link_to_fox_article, fox_news_content) and 
        verify_article_existence(link_to_cnn_article, cnn_content) and
        verify_article_existence(title_of_cnn_article, cnn_content) and
        verify_article_existence(title_of_fox_article, fox_news_content)):
    exit(1)


def verify_LLM_answer(cnn_title, fox_title):
    answer = client_anthropic.messages.create(
        model="claude-3-5-sonnet-20240620",
        #model="claude-3-opus-20240229",
        #model="claude-3-haiku-20240307",
        max_tokens=2000,
        temperature=0,
        system="You are a superior LLM that verifiers work of an inferior LLM. The inferior LLM often makes mistakes, and you are the expert at finding those mistakes. \
You will receive a pair of article titles that were returned by the inferior LLM. \
The title of the first article is provided within the <CNN_article></CNN_article> tag. \
The title of the second article is provided within the <FOX_article></FOX_article> tag. \
Read the titles of these articles carefully and remember them all because I will give you an important task related to these articles.",

        messages=[
            {
                "role": "user",
                "content": [
                {
                    "type": "text",
                    "text": f"<CNN_article>\n{cnn_title}\n</CNN_article>\n\n\n <FOX_article>\n{fox_title}\n</FOX_article>\n\n\n \
The inferior LLM produced this output when I gave it the following prompt: \
<prompt> \
By comparing article titles, find a pair of corresponding articles on CNN and FOX News that describe the same event or news. \
You might notice many potential pairs like that, but only output one pair that you are most certain is on the exact same topic. \
Your output needs to absolutely meet all the following requirements: \
* You need to be 100 percent sure that EXACTLY the same topic is discussed, not just sounding similar. \
* If you cannot find a matching pair of articles where you are 100 percent sure they are about exactly the same topic, just say that you cannot find it, don't try to make up an answer. \
It's perfectly fine if you cannot find a matching pair of articles. \
</prompt> \
Your task as the superior LLM is to verify whether the inferior LLM provided article titles that perfectly match the requirements in the <prompt></prompt> tag. \
\nBefore providing your final judgement, please think about it step-by-step within <thinking></thinking> tags. Then, provide your final judgement within <answer></answer> tags. \
At the end, provide a one-word final judgement: either <final_judgement>Correct</final_judgement> or <final_judgement>Incorrect</final_judgement>.",
                }
            ]
            }
        ]
    )
    # print (answer)
    return answer.content[0].text


LLM_verification_judgement = verify_LLM_answer(title_of_cnn_article, title_of_fox_article)

print (LLM_verification_judgement)

outcome_of_LLM_verification = extract_text_from_tags(LLM_verification_judgement, 'final_judgement')

if outcome_of_LLM_verification == 'Incorrect':
    print ("The LLM made a mistake. Please try again.")
    exit (1)



# Save links to file after all extractions and verifications are done
save_links_to_file([link_to_cnn_article, link_to_fox_article])



def retrieve_cnn_article(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    article = soup.find('article', class_="article--lite")
    if article:
        # Replace common block-level tags with a space before getting text
        for tag in article.find_all(['p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            tag.insert_before(soup.new_string(' '))
        return ' '.join(article.get_text(separator=' ', strip=True).split())
    else:
        return "Article content not found"
    

def retrieve_fox_article(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    div = soup.find('div', class_="page-content")
    if div:
        # Replace common block-level tags with a space before getting text
        for tag in div.find_all(['p', 'div', 'br']):
            tag.insert_before(soup.new_string(' '))
        return ' '.join(div.get_text(separator=' ', strip=True).split())
    else:
        return "div not found"


retrieved_cnn_article = retrieve_cnn_article(link_to_cnn_article)
retrieved_fox_article = retrieve_fox_article(link_to_fox_article)
print (retrieved_cnn_article)
print (retrieved_fox_article)

final_comparison = ''
final_comparison += '\n\n***** The following two articles were compared:\n'
final_comparison += f"CNN title: {title_of_cnn_article}\n"
final_comparison += f"CNN link: {link_to_cnn_article}\n\n"
final_comparison += f"Fox title: {title_of_fox_article}\n"
final_comparison += f"Fox link: {link_to_fox_article}\n\n"


def compare_articles(cnn_content, fox_news_content):
    answer = client_anthropic.messages.create(
        model="claude-3-5-sonnet-20240620",
        #model="claude-3-opus-20240229",
        #model="claude-3-haiku-20240307",
        max_tokens=2000,
        temperature=0,
        system="You are an expert at reading news, analyzing them, and answering questions about them. You will receive \
two articles: one published by CNN, and one publish by Fox News. These articles describe the same topic. \
Your task is to compare the two articles and find the most important differences between them. \
Find out if there are any biases or other indications that the articles are not completely objective. \
Before providing the final answer, please think about it step-by-step within <thinking></thinking> tags. Then, provide your final answer within <answer></answer> tags. \
If you don't know the answer, just say that you don't know how to answer it, don't try to make up an answer.",
        messages=[
            {
                "role": "user",
                "content": [
                {
                    "type": "text",
                    "text": f"<CNN article>\n{cnn_content}\n</CNN article>\n\n\n <FOX News article>\n{fox_news_content}\n</FOX News article>",
                }
            ]
            }
        ]
    )
    # print (answer)
    return answer.content[0].text
    

final_comparison += compare_articles(retrieved_cnn_article, retrieved_fox_article)

print (final_comparison)


#prepare Markdown output for Gist
def parse_input(input_text):
    # Split the input into sections
    sections = re.split(r'<(\w+)>', input_text)
    articles_section = sections[0]
    thinking_section = sections[2].replace('</thinking>', '').strip() if len(sections) > 2 else ""
    answer_section = sections[4].replace('</answer>', '').strip() if len(sections) > 4 else ""


    # Parse the articles section
    articles = {}
    for line in articles_section.strip().split('\n')[1:]:  # Skip the first line
        if 'title:' in line:
            source, title = line.split('title:', 1)
            source = source.strip().replace(':', '')
            articles[source] = {'title': title.strip()}
        elif 'link:' in line:
            source, link = line.split('link:', 1)
            source = source.strip().replace(':', '')
            articles[source]['link'] = link.strip()

   # Parse the thinking section, removing XML tags
    thinking = re.sub(r'<.*?>', '', thinking_section).strip()
    thinking = [line.strip() for line in thinking.split('\n') if line.strip()]

    # Parse the answer section, removing XML tags
    answer = re.sub(r'<.*?>', '', answer_section).strip()
    answer = [line.strip() for line in answer.split('\n') if line.strip()]

    return articles, thinking, answer

def generate_markdown(articles, thinking, answer):
    markdown = f"# News Analysis: {title_of_cnn_article}\n\n"
    markdown += f"*Analysis generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

    # Articles table
    markdown += "## Articles Compared\n\n"
    markdown += "| Source | Title | Link |\n"
    markdown += "|--------|-------|------|\n"
    for source, data in articles.items():
        markdown += f"| {source} | {data['title']} | [Link]({data['link']}) |\n"
    markdown += "\n"

    # Key Comparisons and Analysis
    markdown += "## Key Comparisons and Analysis\n\n"
    for point in thinking:
        markdown += f"{point}  \n"
    markdown += "\n"

    # Conclusion
    markdown += "## Conclusion\n\n"
    for point in answer:
        markdown += f"{point}  \n\n"

    markdown += "---\n\n*This analysis was generated automatically. For the most current and accurate information, please refer to the original sources.*"

    return markdown

def format_news_analysis(input_text):
    articles, thinking, answer = parse_input(input_text)
    return generate_markdown(articles, thinking, answer)

formatted_output = format_news_analysis(final_comparison)
print(formatted_output)




def update_gist(new_content, filename="CNNvsFOX.md"):
    url = f"https://api.github.com/gists/b201790600b088189610788f4c3df51e"
    headers = {
        "Authorization": f"token {os.environ.get('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github.v3+json"
    }

    # First, get the current content
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Failed to fetch current gist content")
        return False

    current_content = response.json()['files'][filename]['content']

    # Prepend new content with a timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated_content = f"--- New Update: {timestamp} ---\n{new_content}\n\n{current_content}"

    # Update the gist with the combined content
    data = {
        "files": {
            filename: {
                "content": updated_content
            }
        }
    }
    response = requests.patch(url, headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"Failed to update gist. Status code: {response.status_code}")
        return False
    
    return True


success = update_gist(formatted_output)
print(f"Gist update {'successful' if success else 'failed'}")
