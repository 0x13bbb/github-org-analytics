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

CONFIG = loadConfig()

logging.basicConfig(filename='org_analysis.log', filemode='w', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class OrgAnalysisConfig:
  def __init__(self, orgName, perPage=100, numCommits=100, pieChartThreshold=0.02, ignoreForks=True, outputDir="output/"):
    self.ORG_NAME = orgName
    self.PER_PAGE = 100
    self.NUM_COMMITS = 100
    self.PIE_CHART_THRESHOLD = 0.02
    self.IGNORE_FORKS = True
    self.OUTPUT_PATH = f"{outputDir}/{self.ORG_NAME}/"

ORG_URL = "https://api.github.com/orgs/{org_name}"
ORG_MEMBERS_URL = "https://api.github.com/orgs/{org_name}/members"
ORG_REPO_URL = "https://api.github.com/orgs/{org_name}/repos?page={page}&per_page={per_page}"

USER_URL = "https://api.github.com/users/{login}"
USER_ORGS_URL = "https://api.github.com/users/{login}/orgs"

REPO_FULL_URL = "https://api.github.com/repos/{org_name}/{repo_name}"
REPO_COLLAB_URL = "https://api.github.com/repos/{org_name}/{repo_name}/collaborators"
REPO_COMMITS_URL = "https://api.github.com/repos/{org_name}/{repo_name}/commits?page={page}&per_page={per_page}"
# COMMIT_COLUMNS = {'login': [], 'avatar_url':[],  'type': [], 'date': [], 'isFork':[]}
# REPO_COLUMNS = {'name':[], 'description': [], 'updated_at': [], 'created_at': [], 'size':[], 'stars': [], 'watchers': [],  'language':[], "issues":[], "license": [], "isFork": [], "forkOf": []}

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

def org_info(json):
  if json == None:
    logger.info(f"No org found with the name {ANALYSIS_CONFIG.ORG_NAME}. Exiting...")
    exit()

  logger.info(f"Name: {json.get('name')}")
  logger.info(f"Created at: {json.get('created_at')}")
  logger.info(f"Updated at: {json.get('updated_at')}")
  logger.info(f"Number of public repos: {json.get('public_repos')}")
  logger.info(f"Number of followers: {json.get('followers')}")

def print_commit_info(i):
  pretty_json(i)
  # logger.info(f"Author: {i.get('author').get('login')}") # TODO: author object may be missing
  # logger.info(f"Avatar: {i.get('author').get('avatar_url')}")
  # logger.info(f"Type: {i.get('author').get('type')}")
  # logger.info(f"Date: {i.get('commit').get('committer').get('date')}")
  # logger.info(f"Message: {i.get('commit').get('message')}") # TODO: feed this and summarise with AI?
  # logger.info(f"Name: {i.get('committer').get('name')}")

def commit_info(j, isFork):
  commit_data = {'login': [], 'avatar_url':[],  'type': [], 'date': [], 'isFork':[]}

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

  df = pd.DataFrame(commit_data)
  df['date'] = pd.to_datetime(df['date']).dt.date
  return df

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
  plt.figure(figsize=(8, 6))
  plt.hist(df, bins=30, edgecolor='black')

  plt.xlabel(xlabel)
  plt.ylabel(ylabel)
  plt.title(title)
  plt.xticks(rotation=45)

  plt.grid(True)
  plt.savefig(f"{fileDir}{fileName}_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.png")

def create_pie(countSlice, labelSlice, title, fileName, fileDir):
  def my_autopct(pct):
    return f'{pct:.1f}%' if pct >= ANALYSIS_CONFIG.PIE_CHART_THRESHOLD * 100 else ''

  texts = [text if size/countSlice.sum() >= ANALYSIS_CONFIG.PIE_CHART_THRESHOLD else '' for size, text in zip(countSlice, labelSlice)]

  plt.figure(figsize=(10,10))
  plt.pie(countSlice, radius=1.6, labels=texts, autopct=my_autopct, startangle=180, labeldistance=1.2, textprops={'fontsize': 10})
  plt.axis('equal')
  plt.title(title, pad=50, loc='center')
  plt.savefig(f"{fileDir}{fileName}_{datetime.now().isoformat(timespec='seconds').replace(':', '-')}.png")

def aggRepo(json, analysisConfig: OrgAnalysisConfig):
  count = 10 # len(json) # used for testing to limit the number of repo's analysed
  commitStats = pd.DataFrame({'login': [], 'avatar_url':[],  'type': [], 'date': [], 'isFork':[]})
  repoStats = pd.DataFrame({'name':[], 'description': [], 'updated_at': [], 'created_at': [], 'size':[], 'stars': [], 'watchers': [],  'language':[], "issues":[], "license": [], "isFork": [], "forkOf": []})

  for i in json:
    # print_repo_info(i)
    repoData = {'name':[], 'description': [], 'updated_at': [], 'created_at': [], 'size':[], 'stars': [], 'watchers': [],  'language':[], "issues":[], "license": [], "isFork": [], "forkOf": []}
    repoData['name'].append(i.get('name'))
    repoData['description'].append(i.get('description'))
    repoData['updated_at'].append(i.get('updated_at'))
    repoData['created_at'].append(i.get('created_at'))
    repoData['size'].append(i.get('size'))
    repoData['stars'].append(i.get('stargazers_count'))
    repoData['watchers'].append(i.get('watchers_count'))
    repoData['language'].append(i.get('language'))
    repoData['issues'].append(i.get('open_issues_count'))

    if i.get('fork') == True:
      # logger.info(f"Repo: {ANALYSIS_CONFIG.ANALYSIS_CONFIG.ORG_NAME}/{i.get('name')} is a fork. Checking parent...")
      repoData['isFork'].append(True)
      full_repo_json = make_request(REPO_FULL_URL.format(org_name=analysisConfig.ORG_NAME, repo_name=i.get('name')))
      if full_repo_json:
        repoData["forkOf"].append(full_repo_json.get("parent").get("full_name"))
    else:
      # logger.info(f"Repo: {ANALYSIS_CONFIG.ANALYSIS_CONFIG.ORG_NAME}/{i.get('name')} is not a fork. Reading commits...")
      repoData['isFork'].append(False)
      repoData['forkOf'].append(None)

    if i.get('fork') == False or analysisConfig.IGNORE_FORKS == False:
      commits_json = make_paged_request(REPO_COMMITS_URL, analysisConfig.NUM_COMMITS, analysisConfig, repo_name=i.get('name'))
      commitStats = pd.concat([commitStats, commit_info(commits_json, False)], ignore_index=True)

    if i.get('license') != None:
      repoData['license'].append(i.get('license').get('name'))
    else:
      repoData['license'].append("None")

    repoDataDF = pd.DataFrame(repoData)
    repoStats = pd.concat([repoStats, repoDataDF], ignore_index=True)

    count -= 1
    if count <= 0:
      break

  logger.info(f"Done fetching repos for the {ANALYSIS_CONFIG.ORG_NAME} organization.\n")

  forkedRepos = repoStats[repoStats['isFork'] == True]
  forkedRepos = forkedRepos.loc[:, ['name', 'forkOf']]
  forkedRepos.drop_duplicates(inplace=True)

  return repoStats, commitStats, forkedRepos

def repoOutput(repoStats, commitStats, analysisConfig: OrgAnalysisConfig):
  logger.info(f"Repos for {analysisConfig.ORG_NAME} GitHub analytics")
  # if repoStats:
  # display(HTML(repoStats.to_html(index=False))) TODO: output to CSV

  if repoStats.empty == False:
    create_histogram(repoStats["stars"], "Number of stars", "Frequency", f'{analysisConfig.ORG_NAME}: Histogram of stars', f"{analysisConfig.ORG_NAME}_stars", analysisConfig.OUTPUT_PATH)
    create_histogram(repoStats["watchers"], "Number of watchers", "Frequency", f'{analysisConfig.ORG_NAME}: Histogram of watchers', f"{analysisConfig.ORG_NAME}_watchers", analysisConfig.OUTPUT_PATH)
    create_histogram(repoStats["issues"], "Number of issues", "Frequency", f'{analysisConfig.ORG_NAME}: Histogram of issues', f"{analysisConfig.ORG_NAME}_issues", analysisConfig.OUTPUT_PATH)
    create_histogram(repoStats["size"], "Size", "Frequency", f'{analysisConfig.ORG_NAME}: Histogram of sizes (kBs)', f"{analysisConfig.ORG_NAME}_sizes", analysisConfig.OUTPUT_PATH)

    by_language = repoStats.groupby('language')["name"].count()
    by_language = by_language.sort_values(ascending=False)
    create_pie(by_language, by_language.index, f"{analysisConfig.ORG_NAME} repos by language", f"{analysisConfig.ORG_NAME}_languages", analysisConfig.OUTPUT_PATH)

  if commitStats.empty == False:
    commitData = commitStats.groupby("date").agg({"avatar_url": "count"}).reset_index()
    commitData.sort_values("date", inplace=True)
    commitData.rename(columns={'avatar_url': 'count'}, inplace=True)
    commitData.set_index('date', inplace=True)
    create_histogram(commitData.index, "Date", "Number of commits", f'{analysisConfig.ORG_NAME}: Histogram of commits', f"{analysisConfig.ORG_NAME}_commits", analysisConfig.OUTPUT_PATH)

    by_author = commitStats.groupby('login').agg({"avatar_url": "count", "type": "first"})
    by_author = by_author.sort_values("avatar_url", ascending=False)
    author_label = by_author.index.map(lambda x: f"{by_author.loc[x]['type']}:{x}")
    create_pie(by_author["avatar_url"], author_label, f"{analysisConfig.ORG_NAME} commit authors for the last {analysisConfig.NUM_COMMITS} commits", f"{analysisConfig.ORG_NAME}_authors", analysisConfig.OUTPUT_PATH)


def repo_info(json, analysisConfig: OrgAnalysisConfig):
  if json == None:
    logger.info(f"No repos found for {analysisConfig.ORG_NAME}. Exiting...")
    exit()

  # call repoStats
  repoStats, commitStats, forkedRepos = aggRepo(json, analysisConfig)

  if len(forkedRepos) > 0:
    logger.info(f"Forked repos for {analysisConfig.ORG_NAME}")
    # display(HTML(forkedRepos.to_html(index=False))) TODO: output this to CSV
  else:
    logger.info(f"There are no forked repos on the {analysisConfig.ORG_NAME} organization.\n")

  if analysisConfig.IGNORE_FORKS:
    commitStats = commitStats[(commitStats["type"] != "Bot") & (commitStats["isFork"] == False)]
    repoStats = repoStats[repoStats["isFork"] == False]

  if len(repoStats) <= 0:
    logger.info(f"There are no repositories on the {analysisConfig.ORG_NAME} organization. Not generating graphs. Exiting... ")
    return

  if len(commitStats) <= 0:
    logger.info(f"There are no commits on repos on the {analysisConfig.ORG_NAME} organization. Not generating graphs. Exiting... ")
    return

  # TODO: generate image files to /ANALYSIS_CONFIG.ORG_NAME dir
  logger.info(f"Showing GitHub analytics for {analysisConfig.ORG_NAME}")
  repoOutput(repoStats, commitStats, analysisConfig)

  

def org_members_info(j):
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
  container = "<div style='width: 100%; display: flex; flex-wrap: wrap; justify-content: center; margin-top: 10px'>"
  for i in htmllist:
    container += i["html"]
  container += "</div>"
  # display(HTML(container)) TODO: output this to file

def main(analysisConfig: OrgAnalysisConfig):
    logger.info(f"STARTED: GitHub organisation analytics for {analysisConfig.ORG_NAME}.")
    
    logger.info(f"1. Org info for {analysisConfig.ORG_NAME}...")
    org_json = make_request(ORG_URL.format(org_name=analysisConfig.ORG_NAME))
    org_info(org_json)

    # logger.info(f"2. Public org member info for {analysisConfig.ORG_NAME}...")
    # org_members_json = make_request(ORG_MEMBERS_URL.format(org_name=analysisConfig.ORG_NAME))
    # org_members_info(org_members_json)

    logger.info(f"3. Repo and commit info for: {analysisConfig.ORG_NAME}...")
    repo_json = make_paged_request(ORG_REPO_URL, org_json.get('public_repos'), analysisConfig)
    # pretty_json(repo_json)
    repo_info(repo_json, analysisConfig)

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