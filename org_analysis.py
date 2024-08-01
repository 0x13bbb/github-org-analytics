import requests
import json
import matplotlib.pyplot as plt
import math
import argparse
from config import loadConfig
import pandas as pd

CONFIG = loadConfig()

ORG_NAME = "pendle-finance"
PER_PAGE = 100
NUM_COMMITS = 100
PIE_CHART_THRESHOLD = 0.02
IGNORE_FORKS = True

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

def make_paged_request(url, num_entries, per_page=PER_PAGE, org_name=ORG_NAME, repo_name=""):
  resp = []
  i = 1
  while num_entries > 0:
    if num_entries < per_page:
      per_page = num_entries

    if repo_name == "":
      resp += make_request(url.format(org_name=org_name, page=i, per_page=per_page))
    else:
      resp += make_request(url.format(org_name=org_name, repo_name=repo_name, page=i, per_page=per_page))
    num_entries -= per_page
    i += 1

  return resp

def make_request(url):
  print(f"Attempting GET: {url}") # TODO: logging

  headers = {
      "Authorization": "Bearer " + CONFIG['GITHUB_API_KEY'],
      "X-GitHub-Api-Version": "2022-11-28"
  }

  response = requests.get(url, headers=headers)

  if response.status_code == 200:
      return response.json()
  else:
      print(f"ERROR: {response.status_code}") # TODO: handle rate limit

def pretty_json(j):
  print(json.dumps(j, indent=2))

def org_info(j):
  print()
  print(f"Name: {j.get('name')}")
  print(f"Created at: {j.get('created_at')}")
  print(f"Updated at: {j.get('updated_at')}")
  print(f"Number of public repos: {j.get('public_repos')}")
  print(f"Number of followers: {j.get('followers')}")
  print()

def print_commit_info(i):
  pretty_json(i)
  # print(f"Author: {i.get('author').get('login')}") # TODO: author object may be missing
  # print(f"Avatar: {i.get('author').get('avatar_url')}")
  # print(f"Type: {i.get('author').get('type')}")
  # print(f"Date: {i.get('commit').get('committer').get('date')}")
  # print(f"Message: {i.get('commit').get('message')}") # TODO: feed this and summarise with AI?
  # print(f"Name: {i.get('committer').get('name')}")

def commit_info(j, isFork):
  commit_data = {'login': [], 'avatar_url':[],  'type': [], 'date': [], 'isFork':[]}

  for i in j:
    print_commit_info(i)
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
  print(f"Name: {i.get('name')}")
  print(f"Description: {i.get('description')}")
  print(f"Created at: {i.get('created_at')}")
  print(f"Updated at: {i.get('updated_at')}")
  print(f"Size: {i.get('size')}kB")
  print(f"Num stars: {i.get('stargazers_count')}")
  print(f"Num watchers: {i.get('watchers_count')}")
  print(f"Language: {i.get('language')}")
  print(f"Open issues: {i.get('open_issues_count')}")

def create_histogram(df, xlabel, ylabel, title):
  plt.figure(figsize=(8, 6))
  plt.hist(df, bins=30, edgecolor='black')

  plt.xlabel(xlabel)
  plt.ylabel(ylabel)
  plt.title(title)
  plt.xticks(rotation=45)

  plt.grid(True)
  plt.show() # TODO: output this to file

def create_pie(countSlice, labelSlice, title):
  def my_autopct(pct):
    return f'{pct:.1f}%' if pct >= PIE_CHART_THRESHOLD * 100 else ''

  texts = [text if size/countSlice.sum() >= PIE_CHART_THRESHOLD else '' for size, text in zip(countSlice, labelSlice)]

  plt.figure(figsize=(10,10))
  plt.pie(countSlice, radius=1.6, labels=texts, autopct=my_autopct, startangle=180, labeldistance=1.2, textprops={'fontsize': 10})
  plt.axis('equal')
  plt.title(title, pad=50, loc='center')
  plt.show() # TODO: output this to file

def repo_info(j):
  count = len(j)
  commitStats = pd.DataFrame({'login': [], 'avatar_url':[],  'type': [], 'date': [], 'isFork':[]})
  repoStats = pd.DataFrame({'name':[], 'description': [], 'updated_at': [], 'created_at': [], 'size':[], 'stars': [], 'watchers': [],  'language':[], "issues":[], "license": [], "isFork": [], "forkOf": []})

  for i in j:
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
      # print(f"Repo: {ORG_NAME}/{i.get('name')} is a fork. Checking parent...")
      repoData['isFork'].append(True)
      full_repo_json = make_request(REPO_FULL_URL.format(org_name=ORG_NAME, repo_name=i.get('name')))
      repoData["forkOf"].append(full_repo_json.get("parent").get("full_name"))
    else:
      # print(f"Repo: {ORG_NAME}/{i.get('name')} is not a fork. Reading commits...")
      repoData['isFork'].append(False)
      repoData['forkOf'].append(None)

    if i.get('fork') == False or IGNORE_FORKS == False:
      commits_json = make_paged_request(REPO_COMMITS_URL, NUM_COMMITS, org_name=ORG_NAME, repo_name=i.get('name'))
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

  print(f"Done fetching repos for the {ORG_NAME} organization.\n")

  forkedRepos = repoStats[repoStats['isFork'] == True]
  forkedRepos = forkedRepos.loc[:, ['name', 'forkOf']]
  forkedRepos.drop_duplicates(inplace=True)

  if len(forkedRepos) > 0:
    print(f"Forked repos for {ORG_NAME}")
    # display(HTML(forkedRepos.to_html(index=False))) TODO: output this to CSV
    print()
  else:
    print(f"There are no forked repos on the {ORG_NAME} organization.\n")

  if IGNORE_FORKS:
    commitStats = commitStats[(commitStats["type"] != "Bot") & (commitStats["isFork"] == False)]
    repoStats = repoStats[repoStats["isFork"] == False]

  if len(repoStats) <= 0:
    print(f"There are no repositories on the {ORG_NAME} organization. Not generating graphs. Exiting... ")
    return

  if len(commitStats) <= 0:
    print(f"There are no commits on repos on the {ORG_NAME} organization. Not generating graphs. Exiting... ")
    return

  # TODO: generate image files to /ORG_NAME dir
  print(f"Showing GitHub analytics for {ORG_NAME}")

  print(f"Repos for {ORG_NAME} GitHub analytics")
  # display(HTML(repoStats.to_html(index=False))) TODO: output to CSV
  print()

  create_histogram(repoStats["stars"], "Number of stars", "Frequency", f'{ORG_NAME}: Histogram of stars')
  create_histogram(repoStats["watchers"], "Number of watchers", "Frequency", f'{ORG_NAME}: Histogram of watchers')
  create_histogram(repoStats["issues"], "Number of issues", "Frequency", f'{ORG_NAME}: Histogram of issues')
  create_histogram(repoStats["size"], "Size", "Frequency", f'{ORG_NAME}: Histogram of sizes (kBs)')

  data = commitStats.groupby("date").agg({"avatar_url": "count"}).reset_index()
  data.sort_values("date", inplace=True)
  data.rename(columns={'avatar_url': 'count'}, inplace=True)
  data.set_index('date', inplace=True)
  create_histogram(data.index, "Date", "Number of commits", f'{ORG_NAME}: Histogram of commits')

  by_language = repoStats.groupby('language')["name"].count()
  by_language = by_language.sort_values(ascending=False)
  create_pie(by_language, by_language.index, f"{ORG_NAME} repos by language")

  by_author = commitStats.groupby('login').agg({"avatar_url": "count", "type": "first"})
  by_author = by_author.sort_values("avatar_url", ascending=False)
  author_label = by_author.index.map(lambda x: f"{by_author.loc[x]['type']}:{x}")
  create_pie(by_author["avatar_url"], author_label, f"{ORG_NAME} commit authors for the last {NUM_COMMITS} commits")

def org_members_info(j):
  if len(j) == 0:
    print("No public org members.\n")
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

def main():
    print(f"STARTED: GitHub organisation analytics for {ORG_NAME}.\n")
    print(f"1. Org info for {ORG_NAME}...")
    org_json = make_request(ORG_URL.format(org_name=ORG_NAME))

    if org_json == None:
        print(f"No org found with the name {ORG_NAME}. Exiting...")
        exit()

    org_info(org_json)

    print(f"2. Public org member info for {ORG_NAME}...")
    org_members_json = make_request(ORG_MEMBERS_URL.format(org_name=ORG_NAME))
    org_members_info(org_members_json)

    print(f"3. Repo and commit info for: {ORG_NAME}...")
    repo_json = make_paged_request(ORG_REPO_URL, org_json.get('public_repos'))
    repo_info(repo_json)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Repository analysis script",
        epilog="Example: python org.py --org-name pendle-finance --num-commits 100 --ignore-forks True --pie-chart-threshold 0.02"
    )

    parser.add_argument("--org-name", default="", help="Organization name", required=True)
    parser.add_argument("--num-commits", type=int, default=100, help="Number of commits to analyze")
    parser.add_argument("--ignore-forks", type=bool, default=True, help="Ignore forked repositories")
    parser.add_argument("--pie-chart-threshold", type=float, default=0.02, help="Pie chart threshold")

    args = parser.parse_args()

    ORG_NAME = args.org_name
    NUM_COMMITS = args.num_commits
    IGNORE_FORKS = args.ignore_forks
    PIE_CHART_THRESHOLD = args.pie_chart_threshold

    main()