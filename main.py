# %%
from __future__ import print_function

import datetime
import os.path
import pickle
from collections import Counter
from dateutil.parser import parse

import pandas as pd
import pytz
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import json


# %%
def get_creds():
    """
    Use "OAuth 2.0 Client IDs". Do not use "Service Account" since it would show the tasks from that account.

    Get credentials from:
    https://console.cloud.google.com/welcome?project=tasks-fetch
    -> APIs & Services
    -> Credentials
    -> OAuth 2.0 Client IDs
    -> Download JSON
    """
    # Specify the scopes required for your application
    SCOPES = ["https://www.googleapis.com/auth/tasks.readonly"]

    creds = None
    token_file = "token.pickle"
    credentials_file = "client_secret.json"

    # Check if token.pickle exists, which contains the user's access and refresh tokens
    if os.path.exists(token_file):
        with open(token_file, "rb") as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_file, "wb") as token:
            pickle.dump(creds, token)

    return creds


creds = get_creds()

# %%
service = build("tasks", "v1", credentials=creds)


# %%
def get_tasks_lists():
    try:
        # Call the Tasks API
        results = service.tasklists().list(maxResults=10).execute()
        task_lists = results.get("items", [])

        if not task_lists:
            print("No task lists found.")
            return

        print("Task lists:")
        for task_list in task_lists:
            print("{0} ({1})".format(task_list["title"], task_list["id"]))

    except HttpError as err:
        print(err)


get_tasks_lists()


# %%
def get_tasks(tasklist_id):
    # Fetch tasks joung tasks (<30 days ago)
    time_delta = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=30)
    tasks = (
        service.tasks()
        .list(
            tasklist=tasklist_id,
            showCompleted=True,
            showHidden=True,
            maxResults=100,  # Max allowed is 100
            updatedMin=time_delta.isoformat(),
        )
        .execute()
    )
    tasks = pd.DataFrame(tasks["items"])
    return tasks


# My Activities (MTYyODI1NjY5Nzc5OTU1MzA4OTU6MDow)
tasks = get_tasks("MTYyODI1NjY5Nzc5OTU1MzA4OTU6MDow")
# tasks


# %%
def clean_tasks(tasks):
    tasks.loc[:, "updated"] = pd.to_datetime(tasks["updated"])
    tasks.loc[:, "notes"] = tasks["notes"].fillna("")
    tasks.loc[:, "completed"] = pd.to_datetime(tasks["completed"])
    return tasks


tasks_filt = clean_tasks(tasks)
tasks_filt.head()


# %% [markdown]
# # Notion
#

# %%
token = auth=os.environ["NOTION_API_TOKEN"]
databaseID = "2de0f27ab58e4c74a9067c92ca7cc07a"
headers = {
    "Authorization": "Bearer " + token,
    "Content-Type": "application/json",
    "Notion-Version": "2022-02-22",
}


# %%
def queryDatabase(databaseID, headers, filters):
    writeUrl = f"https://api.notion.com/v1/databases/{databaseID}/query"
    data = {"filter": filters} if filters else {}
    data = json.dumps(data)
    res = requests.request("POST", writeUrl, headers=headers, data=data)
    data = res.json()
    return data


notion_db = queryDatabase(databaseID, headers, {})
# res


# %%
def get_notion_db_items_ids(notion_db) -> list:
    """
    Response example:
    {
        'object': 'list',
        'results': [
            'id': '74062348-f3de-49b1-9974-7b9e29cf41a8',
            ...
            'properties': {
                "ID": {
                    "id": "FQ%5B%3F",
                    "type": "rich_text",
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "N1pUV3BTN0NQRE5XNTQzZQ", "link": None},
                            "annotations": {
                                "bold": False,
                                "italic": False,
                                "strikethrough": False,
                                "underline": False,
                                "code": False,
                                "color": "default",
                            },
                            "plain_text": "N1pUV3BTN0NQRE5XNTQzZQ",
                            "href": None,
                        }
                    ],
                },
                ...
            }
            ...
        ],
        ...
    }
    """
    ids = []
    for page in notion_db["results"]:
        props = page["properties"]
        rich_text = props["ID"]["rich_text"]
        assert len(rich_text) == 1, "Unhandeled case"
        task_id = rich_text[0]["plain_text"]
        notion_id = page["id"]
        ids.append((task_id, notion_id))
    return ids


ids = get_notion_db_items_ids(notion_db)
ids[:3]


# %%
def check_unique_ids(ids):
    # Count number of instances of each Google Tasks ID
    task_ids = [id[0] for id in ids]
    count = Counter(task_ids)
    count.most_common(10)
    # Assert each id is unique
    assert len(task_ids) == len(
        set(task_ids)
    ), f"Duplicate ids, {count.most_common(10)}..."


check_unique_ids(ids)

# %% [markdown]
# # Add records to Notion


# %%
def props_df_to_json(props_df):
    """
    props example:
        kind                                                tasks#task
        id                                      RkVNc0RqTDZ0RXdQcDZDYw
        etag                                         "LTE0NTA0OTIzNDM"
        title                                          Party pre-italy
        updated                              2023-06-11 08:20:55+00:00
        selfLink     https://www.googleapis.com/tasks/v1/lists/MTYy...
        parent                                  R0g3OXp4T3lIZnRZR0RfbQ
        position                                  09999998313528345090
        status                                               completed
        completed                             2023-06-11T08:20:54.000Z
        hidden                                                    True
        links                                                       []
        notes                                    Should be on Saturday
        due                                                        NaN
    """

    props_json = {
        # kind: skip
        "ID": {
            "rich_text": [{"text": {"content": props_df["id"]}}],
        },
        # etag: skip
        "Title": {
            "type": "title",
            "title": [{"type": "text", "text": {"content": props_df["title"]}}],
        },
        # Removed since it's confusing
        # "Updated": {
        #     "date": {"start": props_df["updated"].strftime("%Y-%m-%d")},
        # },
        "SelfLink": {
            "url": props_df["selfLink"],
        },
        "Position": {
            "number": int(props_df["position"]),
        },
        "Status": {
            "checkbox": True if props_df["status"] == "completed" else False,
        },
        # hidden: skip
        # links: skip
        "Notes": {
            "rich_text": [{"text": {"content": props_df["notes"]}}],
        },
        # due: skip
    }
    if not pd.isnull(props_df["completed"]):
        props_json["Completed"] = {
            "date": {"start": props_df["completed"].strftime("%Y-%m-%d")},
        }
    return props_json


props_json = props_df_to_json(tasks_filt.iloc[1])


# %%
def addPageDatabase(databaseID, headers, props_json):
    writeUrl = f"https://api.notion.com/v1/pages"
    data = {
        "parent": {
            "type": "database_id",
            "database_id": databaseID,
        },
        "properties": props_json,
    }
    data = json.dumps(data)
    try:
        res = requests.request("POST", writeUrl, headers=headers, data=data)
        res.raise_for_status()
    except Exception as _:
        print("Error:", res.json())
    data = res.json()
    return data


def updatePageDatabase(page_id_notion, headers, props_json):
    writeUrl = f"https://api.notion.com/v1/pages/{page_id_notion}"
    data = {"properties": props_json}
    data = json.dumps(data)
    try:
        res = requests.request("PATCH", writeUrl, headers=headers, data=data)
        res.raise_for_status()
    except Exception as _:
        print("Error:", res.json())
    data = res.json()
    return data


def writeDatabase(databaseID, headers, props_json, id_task):
    ids = get_notion_db_items_ids(notion_db)
    task_ids = [id[0] for id in ids]
    if id_task in task_ids:
        print("-> Paching")
        page_id_notion = [id[1] for id in ids if id[0] == id_task][0]
        updatePageDatabase(page_id_notion, headers, props_json)
    else:
        print("-> Adding")
        addPageDatabase(databaseID, headers, props_json)
    print("===")


# %%
def import_tasks_to_notion():
    for _, props_df in tasks_filt.iterrows():
        print(props_df["title"])
        page_id_tasks = props_df["id"]
        props_json = props_df_to_json(props_df)
        writeDatabase(databaseID, headers, props_json, page_id_tasks)


import_tasks_to_notion()

# %% [markdown]
# # Calculate Weeks Taken

# %%
filters = {
    "property": "Status",
    "checkbox": {
        "equals": True,
    },
}
notion_db = queryDatabase(databaseID, headers, filters)
# notion_db


# %%
def get_time_tuples(notion_db) -> list:
    """
    Example response:
        {
            "object": "list",
            "results": [
                {
                    ...
                    "properties": {
                        "Completed": {
                            "id": "ABbF",
                            "type": "date",
                            "date": {"start": "2023-06-07", "end": None, "time_zone": None},
                        },
                        "Created time": {
                            "id": "D%3BiG",
                            "type": "created_time",
                            "created_time": "2023-06-12T13:41:00.000Z",
                    },
                    ...
                }
            ],
        }
    """
    ids = []
    for page in notion_db["results"]:
        props = page["properties"]
        # Completed
        completed = props["Completed"]["date"]["start"]
        # Created
        created = props["Created time"]["created_time"]
        # ID
        id_rich_text = props["ID"]["rich_text"]
        assert len(id_rich_text) == 1, "Unhandeled case"
        notion_id = page["id"]
        ids.append((notion_id, completed, created))
    return ids


ids = get_time_tuples(notion_db)
# ids


# %%
def add_weeks_taken_to_notion():
    for page_id_notion, completed, created in ids:
        completed = parse(completed).date()
        created = parse(created).date()
        delta = completed - created

        print(f"Delta: {delta.days} days")

        if delta.days < 0:
            print("-> Err: Notion created time > Google Tasks completed time")
            week_label = "Err"
        elif delta.days <= 7:
            week_label = "0 Weeks"
        elif delta.days <= 14:
            week_label = "1 Week"
        elif delta.days <= 21:
            week_label = "2 Weeks"
        else:
            week_label = "3+ Weeks"


        props_json = {
            "Weeks Taken": {
                "select": {"name": week_label},
            },
        }

        updatePageDatabase(page_id_notion, headers, props_json)

add_weeks_taken_to_notion()
