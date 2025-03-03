# Tasks fetch

Import **Google Tasks** to **Notion** and show how much time it took in weeks.

![](assets/image.png)

**Python version: 3.12**


## Setup

Get files:
- *clinet_secret.json.example* -> *clinet_secret.json*  
https://console.cloud.google.com/welcome  
-> APIs & Services  
-> Credentials  
-> OAuth 2.0 Client IDs  
-> Download JSON  


- *.env.example* -> *.env*  
https://www.notion.so/profile/integrations


## Docker

**Warning**: image creation can't be automated with github actions: even with credentials.json the script requires tocken.pickle generated through a browser and login with google account, and refreshed once in a while.

```bash
docker compose up
```
