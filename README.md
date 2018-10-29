# Slacktunes
Adds youtube or spotify links shared on slack to a youtube or spotify playlist

### Local Development
Developing a slack app that uses 3rd party APIs requires more setup than the usual web app.

This guide assumes you already have a slack workspace and are authorized to add apps.

#### Setting up the app
`settings.py` is empty, but imports `local_settings.py` which you should create at the top level of the app directory and which is where you should be adding these properties

Slacktunes uses sqlite for development so add this to `local_settings.py`:
```
local_settings.py

DB_URI = 'sqlite:////tmp/test.db'
SLACKTUNES_USER_ID = <your slack user id>
```

Get your slack user id by:
1. Going to [https://www.slack.com]
1. Navigating to your workspace
1. Copying your id from the url of your private messages channel

To create the initial test db:
```
from app import db
db.create_all()
```

To run the app:
```
python application.py
```

#### Using ngrok
[ngrok][https://ngrok.com/] is an easy way to proxy a randomly generated url to your localhost without setting up any DNS or ssl certificates

In a separate terminal window run:
```
ngrok http <port_your_local_is_running_on>
```
which will output a url that will hereby referred to as `ngrok_url`

Add `ngrok_url` to your `local_settings.py` which should now look like:
```
local_settings.py

DB_URI = 'sqlite:////tmp/test.db'
SLACKTUNES_USER_ID = <your slack user id>
BASE_URI = <ngrok_url>
```

### NOTE:
Every time you shut down ngrok and restart it, you'll have to change any place you're using `ngrok_url`
#### Including:
* slack
* youtube developer apis
* spotify developer apis

#### Creating a Slack App for you workspace
Create a new slack app at [https://api.slack.com/apps]. Name it whatever you want, but might I suggest `slacktunes_local`
##### Oauth & Permissions
To post to slack channels, you'll need an oauth token. The scopes that slacktunes needs are
* channels:history
* chat:write:bot
* commands
* links:read

Add those and click: `Install App to Workspace`

This will give you an oauth token that should be added to `local_settings.py` as `SLACK_OAUTH_TOKEN`

If you look in the `Basic Information` tab of the app page, you should also see `Client Id`, `Client Secret`, and `Verification Token`
Add these to `local_settings.py` as:
```
local_settings.py

DB_URI = 'sqlite:////tmp/test.db'
SLACKTUNES_USER_ID = <your slack user id>
BASE_URI = <ngrok_url>

SLACK_CLIENT_ID = <client id>
SLACK_CLIENT_SECRET = <client secret>
SLACK_OAUTH_TOKEN = <oauth_token>
SLACK_VERIFICATION_TOKEN = <verification_token>
```

##### Slash commands
Slacktunes uses 4 slash commands.
The command is the same as the url to the playlist, e.g.:
```
Command: /<command>
Request URL: <ngrok_url>/<command>

for example:

Command: /create_playlist
Request URL: <ngrok_url>/create_playlist/
```
* create_playlist <playlist_name> <service>
* scrape_music <playlist_name>
* list_playlist
* delete_playlist

##### Event Subscriptions
Turn Event Subscriptions on. Slacktunes needs to subscribe to the `link_shared` event.

Change the `Request URL` to your `ngrok_url`

Slack also requires you to define up to 5 domains which will trigger the `link_shared` event. Slacktunes needs:
* youtube.com
* spotify.com
* youtu.be (for mobile)

#### Getting Youtube & Spotify API keys
Sign up for a [youtube developer account][https://developers.google.com/youtube/]

And a [spotify developer account][https://developer.spotify.com/]

Add the client keys/secrets to your `local_settings.py` file.

```
local_settings.py

DB_URI = 'sqlite:////tmp/test.db'
SLACKTUNES_USER_ID = <your slack user id>
BASE_URI = <ngrok_url>

SLACK_CLIENT_ID = <client id>
SLACK_CLIENT_SECRET = <client secret>
SLACK_OAUTH_TOKEN = <oauth_token>
SLACK_VERIFICATION_TOKEN = <verification_token>

SPOTIFY_CLIENT_ID = <your_spotify_client_id>
SPOTIFY_CLIENT_SECRET = <your_spotify_client_secret>
YOUTUBE_CLIENT_ID = <your_youtube_client_id>
YOUTUBE_CLIENT_SECRET = <your_youtube_client_secret>
```

#### That's it!
You should be good to go. Happy slacktuning!