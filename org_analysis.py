import requests
import json
import matplotlib.pyplot as plt
import math
import argparse
from config import loadConfig
import pandas as pd
import logging
import os
from datetime import datetime
import matplotlib.patheffects as path_effects
from anthropic import Anthropic

CONFIG = loadConfig()

AI_client = Anthropic(
    api_key=CONFIG["ANTHROPIC_API_KEY"]
)

logging.basicConfig(filename='org_analysis.log', filemode='w', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class OrgAnalysisConfig:
  def __init__(self, orgName, perPage=100, numCommits=100, pieChartThreshold=0.02, ignoreForks=True, outputDir="output/"):
    self.ORG_NAME = orgName
    self.PER_PAGE = perPage
    self.NUM_COMMITS = numCommits
    self.PIE_CHART_THRESHOLD = pieChartThreshold
    self.IGNORE_FORKS = True
    self.OUTPUT_PATH = f"{outputDir}/{self.ORG_NAME}/"

  def __str__(self):
    return (f"Organization: {self.ORG_NAME}\n"
            f"Per Page: {self.PER_PAGE}\n"
            f"Number of Commits: {self.NUM_COMMITS}\n"
            f"Pie Chart Threshold: {self.PIE_CHART_THRESHOLD}\n"
            f"Ignore Forks: {self.IGNORE_FORKS}\n"
            f"Output Path: {self.OUTPUT_PATH}")

ORG_URL = "https://api.github.com/orgs/{org_name}"
ORG_MEMBERS_URL = "https://api.github.com/orgs/{org_name}/members"
ORG_REPO_URL = "https://api.github.com/orgs/{org_name}/repos?page={page}&per_page={per_page}"

USER_URL = "https://api.github.com/users/{login}"
USER_ORGS_URL = "https://api.github.com/users/{login}/orgs"

REPO_FULL_URL = "https://api.github.com/repos/{org_name}/{repo_name}"
REPO_COLLAB_URL = "https://api.github.com/repos/{org_name}/{repo_name}/collaborators"
REPO_COMMITS_URL = "https://api.github.com/repos/{org_name}/{repo_name}/commits?page={page}&per_page={per_page}"
# COMMIT_COLUMNS = {'login': [], 'avatar_url':[],  'type': [], 'date': [], 'isFork':[]}
# REPO_COLUMNS = {'name':[], 'description': [], 'updated_at': [], 'created_at': [], 'size':[], 'stars': [], 'watchers': [],  'language':[], "issues":[], "license": [], "isFork": [], "forkOf": [], "AICommitSummary": []}

def make_paged_request(url, num_entries, analysisConfig: OrgAnalysisConfig, repo_name=""):
  resp = []
  i = 1
  per_page = analysisConfig.PER_PAGE
  while num_entries > 0:
    if num_entries < per_page:
      per_page = num_entries

    request_url = ""
    if repo_name:
      request_url = url.format(org_name=analysisConfig.ORG_NAME, repo_name=repo_name, page=i, per_page=per_page)
    else:
      request_url = url.format(org_name=analysisConfig.ORG_NAME, page=i, per_page=per_page)

    result = make_request(request_url)

    if result:
      resp += result

    num_entries -= per_page
    i += 1

  return resp

def make_request(url):
  logger.info(f"Attempting GET: {url}")

  headers = {
      "Authorization": "Bearer " + CONFIG['GITHUB_API_KEY'],
      "X-GitHub-Api-Version": "2022-11-28"
  }

  response = requests.get(url, headers=headers)

  if response.status_code == 200:
      return response.json()
  else:
      logger.info(f"ERROR: {response.status_code}") # TODO: handle rate limit

def pretty_json(j):
  logger.info(json.dumps(j, indent=2))

def org_info(json, analysisConfig: OrgAnalysisConfig):
  if json == None:
    logger.info(f"No org found with the name {analysisConfig.ORG_NAME}. Exiting...")
    exit()

  logger.info(f"Name: {json.get('name')}")
  logger.info(f"Description: {json.get('description')}")
  logger.info(f"Created at: {json.get('created_at')}")
  logger.info(f"Updated at: {json.get('updated_at')}")
  logger.info(f"Number of public repos: {json.get('public_repos')}")
  logger.info(f"Number of followers: {json.get('followers')}")
  # pretty_json(json)
  summary = f"""
Organization summary
Name: {json.get('name')}
Description: {json.get('description')}
Number of followers: {json.get('followers')}
"""
  return summary

def truncate_to_token_limit(text, max_tokens):
    tokens = 0
    words = text.split()
    truncated = []
    
    for word in words:
        word_tokens = AI_client.count_tokens(word)
        if tokens + word_tokens > max_tokens:
            break
        truncated.append(word)
        tokens += word_tokens
    
    return ' '.join(truncated)

def print_commit_info(i):
  pretty_json(i)
  # logger.info(f"Author: {i.get('author').get('login')}") # TODO: author object may be missing
  # logger.info(f"Avatar: {i.get('author').get('avatar_url')}")
  # logger.info(f"Type: {i.get('author').get('type')}")
  # logger.info(f"Date: {i.get('commit').get('committer').get('date')}")
  # logger.info(f"Message: {i.get('commit').get('message')}") # TODO: feed this and summarise with AI?
  # logger.info(f"Name: {i.get('committer').get('name')}")

def commit_info(j, isFork, orgSummary:str, repoSummary: str):
  commit_data = {'login': [], 'avatar_url':[],  'type': [], 'date': [], 'isFork':[]}
  commit_messages = ""
  count = 1
  for i in j:
    # print_commit_info(i)
    if i.get('author') != None:
      commit_data['login'].append(i.get('author').get('login'))
      commit_data['avatar_url'].append(i.get('author').get('avatar_url'))
      commit_data['type'].append(i.get('author').get('type'))
    else:
      commit_data['login'].append(i.get('commit').get('author').get("name"))
      if i.get('committer') != None:
        commit_data['avatar_url'].append(i.get('committer').get('avatar_url'))
        commit_data['type'].append(i.get('committer').get('type'))
      else:
        commit_data['avatar_url'].append(None)
        commit_data['type'].append(None)
    
    commit_data['date'].append(i.get('commit').get('committer').get('date'))
    commit_data['isFork'].append(isFork)

    if "chore" not in i.get('commit').get('message'):
      commit_messages += f"""
Date: {commit_data['date'][-1]}
Message: {i.get('commit').get('message')}
"""
    count+=1

  AI_info = f"""
{orgSummary}
{repoSummary}
{commit_messages}
"""

  AI_info = truncate_to_token_limit(AI_info, 1024)
  logger.info(AI_info)
  logger.info(f"Input tokens: {AI_client.count_tokens(AI_info)}")

  message = AI_client.messages.create(
    max_tokens=1024,
    system=f"You are a software expert working for an investment firm. You are given summaries of a Github organization, a repository, and a list of commits from that repository. Summarise the commit history in two sentences in general terms. Avoid mentioning the specifics of the changes, instead focusing on how the changes affect the repository. Focus on major changes or updates in the repository and ignore non-substantial changes (documentation changes, minor fixes, package tracker updates, etc.) Read between the lines. If there are no major changes or updates, mention this. Identify any potential risks or concerns in the repository in one sentence. Identify how the repository contriubtes to the organization's product in one sentence. Do not mention needed further evaluation or due dilligence needed as this is a given.",
    messages=[
      {
        "role": "user",
        "content": AI_info,
      }
    ],
    model="claude-3-opus-20240229",
  )
  # logger.info(f"AI response: {message.content}")
  logger.info(f"AI response: {message.content[0].text}")
  logger.info(f"AI response tokens: {AI_client.count_tokens(message.content[0].text)}")
  AI_summary = message.content[0].text

  df = pd.DataFrame(commit_data)
  df['date'] = pd.to_datetime(df['date']).dt.date
  return df, AI_summary

def print_repo_info(i):
  # pretty_json(i)
  logger.info(f"Name: {i.get('name')}")
  logger.info(f"Description: {i.get('description')}")
  logger.info(f"Created at: {i.get('created_at')}")
  logger.info(f"Updated at: {i.get('updated_at')}")
  logger.info(f"Size: {i.get('size')}kB")
  logger.info(f"Num stars: {i.get('stargazers_count')}")
  logger.info(f"Num watchers: {i.get('watchers_count')}")
  logger.info(f"Language: {i.get('language')}")
  logger.info(f"Open issues: {i.get('open_issues_count')}")

def create_histogram(df, xlabel, ylabel, title, fileName, fileDir):
  plt.rcParams['font.family'] = ['Quicksand', 'sans-serif']
  plt.rcParams['font.size'] = 12

  fig, ax = plt.subplots(figsize=(12, 12))
  fig.patch.set_facecolor('floralwhite')
  ax.set_facecolor('floralwhite')
  
  ax.hist(df, bins=30, color='lightskyblue', edgecolor='steelblue', linewidth=0.5)
  ax.spines['top'].set_visible(False)
  ax.spines['right'].set_visible(False)

  ax.set_xlabel(xlabel, labelpad=25)
  ax.set_ylabel(ylabel, labelpad=25)
  ax.set_title(title, fontweight='bold', fontsize=16)
  plt.xticks(rotation=45)
  plt.savefig(f"{fileDir}{fileName}_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.png")

def create_pie(countSlice, labelSlice, title, fileName, fileDir, pieChartThreshold):
  def my_autopct(pct):
    return f'{pct:.1f}%' if pct >= pieChartThreshold * 100 else ''

  texts = [text if size/countSlice.sum() >= pieChartThreshold else '' for size, text in zip(countSlice, labelSlice)]

  plt.figure(figsize=(15,15), facecolor='floralwhite')
  
  plt.rcParams['font.family'] = ['Quicksand', 'sans-serif']

  # Create a donut chart by setting a wedge at the center
  center_circle = plt.Circle((0,0), 0.50, fc='floralwhite')

  plt.pie(
    countSlice, 
    radius=1, 
    labels=texts, 
    autopct=my_autopct,
    pctdistance=0.75,
    startangle=180, 
    labeldistance=1.1,
    colors=plt.cm.Set2.colors, 
    wedgeprops={'edgecolor': 'white', 'linewidth': 1},
    textprops={'fontsize': 14}
  )

  # Add the center circle to make it a donut chart
  fig = plt.gcf()
  fig.gca().add_artist(center_circle)

  for text in plt.gca().texts[1::2]:  # Select every other text object (the labels)
    text.set_color('white')
    text.set_fontweight('bold')
    text.set_fontsize(15)
    text.set_fontname('Quicksand')
    text.set_path_effects([path_effects.withStroke(linewidth=1, foreground='gray')])

  plt.axis('equal')
  plt.title(title, pad=70, loc='center', fontweight='bold', fontsize=16)
  plt.savefig(f"{fileDir}{fileName}_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.png")

def aggRepo(json, analysisConfig: OrgAnalysisConfig, orgSummary: str):
  count = 5 # len(json) # used for testing to limit the number of repo's analysed
  commitStats = pd.DataFrame({'login': [], 'avatar_url':[],  'type': [], 'date': [], 'isFork':[]})
  repoStats = pd.DataFrame({'name':[], 'description': [], 'updated_at': [], 'created_at': [], 'size':[], 'stars': [], 'watchers': [],  'language':[], "issues":[], "license": [], "isFork": [], "forkOf": [], "AICommitSummary": []})

  for i in json:
    # print_repo_info(i)
    repoData = {'name':[], 'description': [], 'updated_at': [], 'created_at': [], 'size':[], 'stars': [], 'watchers': [],  'language':[], "issues":[], "license": [], "isFork": [], "forkOf": [], "AICommitSummary": []}
    repoData['name'].append(i.get('name'))
    repoData['description'].append(i.get('description'))
    repoData['updated_at'].append(i.get('updated_at'))
    repoData['created_at'].append(i.get('created_at'))
    repoData['size'].append(i.get('size'))
    repoData['stars'].append(i.get('stargazers_count'))
    repoData['watchers'].append(i.get('watchers_count'))
    repoData['language'].append(i.get('language'))
    repoData['issues'].append(i.get('open_issues_count'))

    repoSummary = f"""
Repository summary:
Name: {i.get('name')}
Description: {i.get('description')}
"""

    if i.get('fork') == True:
      logger.info(f"Repo: {analysisConfig.ORG_NAME}/{i.get('name')} is a fork. Checking parent...")
      repoData['isFork'].append(True)
      full_repo_json = make_request(REPO_FULL_URL.format(org_name=analysisConfig.ORG_NAME, repo_name=i.get('name')))
      if full_repo_json:
        repoData["forkOf"].append(full_repo_json.get("parent").get("full_name"))
    else:
      logger.info(f"Repo: {analysisConfig.ORG_NAME}/{i.get('name')} is not a fork. Reading commits...")
      repoData['isFork'].append(False)
      repoData['forkOf'].append(None)

    if i.get('fork') == False or analysisConfig.IGNORE_FORKS == False:
      commits_json = make_paged_request(REPO_COMMITS_URL, analysisConfig.NUM_COMMITS, analysisConfig, repo_name=i.get('name'))
      commitDF, AICommitSummary = commit_info(commits_json, False, orgSummary, repoSummary)
      commitStats = pd.concat([commitStats, commitDF], ignore_index=True)
      repoData['AICommitSummary'].append(AICommitSummary)
    else:
      repoData['AICommitSummary'].append("None")


    if i.get('license') != None:
      repoData['license'].append(i.get('license').get('name'))
    else:
      repoData['license'].append("None")

    repoDataDF = pd.DataFrame(repoData)
    repoStats = pd.concat([repoStats, repoDataDF], ignore_index=True)

    count -= 1
    if count <= 0:
      break

  logger.info(f"Done fetching repos for the {analysisConfig.ORG_NAME} organization.")

  forkedRepos = repoStats[repoStats['isFork'] == True]
  forkedRepos = forkedRepos.loc[:, ['name', 'forkOf']]
  forkedRepos.drop_duplicates(inplace=True)

  return repoStats, commitStats, forkedRepos

def repoOutput(repoStats, commitStats, analysisConfig: OrgAnalysisConfig):
  logger.info(f"Repos for {analysisConfig.ORG_NAME} GitHub analytics")

  if repoStats.empty == False:
    repoStats.to_json(f"{analysisConfig.OUTPUT_PATH}{analysisConfig.ORG_NAME}_repo_stats_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.json", orient='records')
    create_histogram(repoStats["stars"], "Number of stars", "Frequency", f'{analysisConfig.ORG_NAME}: Histogram of stars', f"{analysisConfig.ORG_NAME}_stars", analysisConfig.OUTPUT_PATH)
    create_histogram(repoStats["watchers"], "Number of watchers", "Frequency", f'{analysisConfig.ORG_NAME}: Histogram of watchers', f"{analysisConfig.ORG_NAME}_watchers", analysisConfig.OUTPUT_PATH)
    create_histogram(repoStats["issues"], "Number of issues", "Frequency", f'{analysisConfig.ORG_NAME}: Histogram of issues', f"{analysisConfig.ORG_NAME}_issues", analysisConfig.OUTPUT_PATH)
    create_histogram(repoStats["size"], "Size", "Frequency", f'{analysisConfig.ORG_NAME}: Histogram of sizes (kBs)', f"{analysisConfig.ORG_NAME}_sizes", analysisConfig.OUTPUT_PATH)

    by_language = repoStats.groupby('language')["name"].count()
    by_language = by_language.sort_values(ascending=False)
    create_pie(by_language, by_language.index, f"{analysisConfig.ORG_NAME} repos by language", f"{analysisConfig.ORG_NAME}_languages", analysisConfig.OUTPUT_PATH, analysisConfig.PIE_CHART_THRESHOLD)

  if commitStats.empty == False:
    commitStats.to_json(f"{analysisConfig.OUTPUT_PATH}{analysisConfig.ORG_NAME}_commit_stats_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.json", orient='records')
    commitData = commitStats.groupby("date").agg({"avatar_url": "count"}).reset_index()
    commitData.sort_values("date", inplace=True)
    commitData.rename(columns={'avatar_url': 'count'}, inplace=True)
    commitData.set_index('date', inplace=True)
    create_histogram(commitData.index, "Date", "Number of commits", f'{analysisConfig.ORG_NAME}: Histogram of commits', f"{analysisConfig.ORG_NAME}_commits", analysisConfig.OUTPUT_PATH)

    by_author = commitStats.groupby('login').agg({"avatar_url": "count", "type": "first"})
    by_author = by_author.sort_values("avatar_url", ascending=False)
    author_label = by_author.index.map(lambda x: f"{by_author.loc[x]['type']}:{x}")
    create_pie(by_author["avatar_url"], author_label, f"{analysisConfig.ORG_NAME} commit authors for the last {analysisConfig.NUM_COMMITS} commits", f"{analysisConfig.ORG_NAME}_authors", analysisConfig.OUTPUT_PATH, analysisConfig.PIE_CHART_THRESHOLD)


def repo_info(json, analysisConfig: OrgAnalysisConfig, orgSummary: str):
  if json == None:
    logger.info(f"No repos found for {analysisConfig.ORG_NAME}. Exiting...")
    exit()

  # call repoStats
  repoStats, commitStats, forkedRepos = aggRepo(json, analysisConfig, orgSummary)

  if len(forkedRepos) > 0:
    logger.info(f"Forked repos for {analysisConfig.ORG_NAME}")
    forkedRepos.to_csv(f"{analysisConfig.OUTPUT_PATH}{analysisConfig.ORG_NAME}_forked_repos_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.csv", index=True)
  else:
    logger.info(f"There are no forked repos on the {analysisConfig.ORG_NAME} organization.")

  if analysisConfig.IGNORE_FORKS:
    commitStats = commitStats[(commitStats["type"] != "Bot") & (commitStats["isFork"] == False)]
    repoStats = repoStats[repoStats["isFork"] == False]

  if len(repoStats) <= 0:
    logger.info(f"There are no repositories on the {analysisConfig.ORG_NAME} organization. Not generating graphs. Exiting... ")
    return

  if len(commitStats) <= 0:
    logger.info(f"There are no commits on repos on the {analysisConfig.ORG_NAME} organization. Not generating graphs. Exiting... ")
    return

  logger.info(f"Showing GitHub analytics for {analysisConfig.ORG_NAME}")
  repoOutput(repoStats, commitStats, analysisConfig)

  AI_repo_summaries = orgSummary
  AI_repo_summaries += '\n'.join([str(x) for x in repoStats['AICommitSummary'] if pd.notna(x)])
  logger.info(f"AI repo summaries: {AI_repo_summaries}")
  logger.info(f"Input tokens: {AI_client.count_tokens(AI_repo_summaries)}")
  message = AI_client.messages.create(
    max_tokens=1024,
    system=f"You are a software expert working for an investment firm. You are given summaries of a Github organization, and commits to its repositories. The investment firm wants to know two key things: if there could be any red flags for the organization, and if there are any opportunities for the organization. You are to summarize the information in a way that is easy to understand for a non-technical person. You are to focus on the opportunities and red flags. You are to be concise and to the point. Do not mention needed further evaluation or due dilligence needed as this is a given. Do not make unsubstantiated claims.",
    messages=[
      {
        "role": "user",
        "content": AI_repo_summaries,
      }
    ],
    model="claude-3-opus-20240229",
  )
  # logger.info(f"AI response: {message.content}")
  logger.info(f"AI response: {message.content[0].text}")
  logger.info(f"AI response tokens: {AI_client.count_tokens(message.content[0].text)}")
  AI_summary = message.content[0].text
  with open(f"{analysisConfig.OUTPUT_PATH}{analysisConfig.ORG_NAME}_AI_summary_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.md", "w") as f:
    f.write(AI_summary)

def org_members_info(j, analysisConfig: OrgAnalysisConfig):
  if len(j) == 0:
    logger.info("No public org members.\n")
    return

  htmllist = []

  for i in j:
    user_json = make_request(USER_URL.format(login=i.get('login')))
    user_org_json = make_request(USER_ORGS_URL.format(login=i.get('login')))
    user_orgs_list = [org.get('login') for org in user_org_json]

    html = "<div style='width: 200px; margin: 10px; text-align: center;'>"
    html += f'<img src="{i.get("avatar_url")}" style="max-width: 100px; height: 100px; border-radius: 50%;">'
    html += f'<div style="margin-top: 5px;"><b>{i.get("login")}</b></div>'
    html += f'<p>Name: {user_json.get("name")}</p>'
    html += f'<p style="word-wrap: break-word">Orgs: {", ".join(user_orgs_list)}</p>'
    html += f'<p>Followers: {user_json.get("followers")}</p>'
    html += f'</div>'

    htmllist.append({"followers": user_json.get("followers"), "html": html})

  htmllist = sorted(htmllist, key=lambda x: x["followers"], reverse=True)
  container = "<div style='width: 100%; display: flex; flex-wrap: wrap; justify-content: center; margin-top: 10px; font-family:\"Quicksand\"'>"
  for i in htmllist:
    container += i["html"]
  container += "</div>"

  with open(f"{analysisConfig.OUTPUT_PATH}{analysisConfig.ORG_NAME}_org_members_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.html", "w") as f:
    f.write(container)

def main(analysisConfig: OrgAnalysisConfig):
    logger.info(f"STARTED: GitHub organisation analytics for {analysisConfig.ORG_NAME}.")
    
    logger.info(f"1. Org info for {analysisConfig.ORG_NAME}...")
    org_json = make_request(ORG_URL.format(org_name=analysisConfig.ORG_NAME))
    org_summary = org_info(org_json, analysisConfig)

    logger.info(f"2. Public org member info for {analysisConfig.ORG_NAME}...")
    org_members_json = make_request(ORG_MEMBERS_URL.format(org_name=analysisConfig.ORG_NAME))
    org_members_info(org_members_json, analysisConfig)

    logger.info(f"3. Repo and commit info for: {analysisConfig.ORG_NAME}...")
    repo_json = make_paged_request(ORG_REPO_URL, org_json.get('public_repos'), analysisConfig)
    # pretty_json(repo_json)
    repo_info(repo_json, analysisConfig, org_summary)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(
      description="Repository analysis script",
      epilog="Example: python org.py --org-name pendle-finance --num-commits 100 --ignore-forks True --pie-chart-threshold 0.02 --output-dir 'output/'"
  )

  parser.add_argument("--org-name", default="", help="Organization name", required=True)
  parser.add_argument("--num-commits", type=int, default=100, help="Number of commits to analyze")
  parser.add_argument("--ignore-forks", type=bool, default=True, help="Ignore forked repositories")
  parser.add_argument("--pie-chart-threshold", type=float, default=0.02, help="Pie chart threshold")
  parser.add_argument("--output-dir", type=str, default="output/", help="Target output directory")

  args = parser.parse_args()
  ANALYSIS_CONFIG = OrgAnalysisConfig(args.org_name, args.num_commits, args.ignore_forks, args.pie_chart_threshold, args.output_dir)

  if not os.path.exists(ANALYSIS_CONFIG.OUTPUT_PATH):
    os.makedirs(ANALYSIS_CONFIG.OUTPUT_PATH)

  print(f"Running analysis for: {ANALYSIS_CONFIG.ORG_NAME}")
  main(ANALYSIS_CONFIG)
  print(f"Done.")