#Slacktunes

Adds youtube or spotify links shared on slack to a youtube or spotify playlist

### Local Development
Developing a slack app that uses 3rd party APIs requires more setup than the usual web app.

This guide assumes you already have a slack workspace and are authorized to add apps.

#### Using ngrok
[ngrok](https://ngrok.com/) is an easy way to proxy a randomly generated url to your localhost without setting up any DNS or ssl certificates

This guide to local dev relies on ngrok and the url that it generates when you use it

In a separate terminal window run:
```
ngrok http 8080
```
which will output a url that will hereby referred to as `ngrok_url`

Add `ngrok_url` to your `dev.env` as `NGROK_URL` 

### NOTE:
Every time you shut down ngrok and restart it, ngrok will generate a new url and you'll have to change any place you're using `ngrok_url`
#### Including:
* dev.env (and then `docker-compose restart`)
* slack (for commands and events)
* youtube developer apis (for oauth callback urls)
* spotify developer apis (for oauth callback urls)


#### Setting up the app
`dev.env` is the environment file used by Docker. It's just a template: you'll have to fill in the values.

To start the app:
```
docker-compose up -d
```

To create the initial test db:
```
docker-compose exec -it slacktunes_backend /bin/bash

COMING SOON: flask db upgrade
```

Your app should now be running! But it needs more setup. Visit `localhost:8080` and also `ngrok_url` in your browser to check that everything is working.

You should see a screen that says `Welcome to Slacktunes`


#### Creating a Slack App for you workspace
Create a new slack app at https://api.slack.com/apps. Name it whatever you want, but might I suggest `slacktunes_local`

##### Oauth & Permissions
To post to slack channels, you'll need an oauth token. The scopes that slacktunes needs are
* channels:history
* chat:write:bot
* commands
* links:read

Add those and click: `Install App to Workspace`

This will give you an oauth token that should be added to `dev.env` as `SLACK_OAUTH_TOKEN`

If you look in the `Basic Information` tab of the app page, you should also see `Client Id`, `Client Secret`, and `Verification Token`
Add these to `dev.env` as:
```
dev.env

BASE_URI = <ngrok_url>

SLACK_CLIENT_ID = <client id>
SLACK_CLIENT_SECRET = <client secret>
SLACK_OAUTH_TOKEN = <oauth_token>
SLACK_VERIFICATION_TOKEN = <verification_token>
```

##### Slash commands
Slacktunes uses 4 slash commands that you should add through the slack apps web UI.
The command is the same as the url to the playlist, e.g.:
```
Command: /<command>
Request URL: <ngrok_url>/<command>

for example:

Command: /create_playlist
Request URL: <ngrok_url>/create_playlist/
```
* create_playlist <playlist_name> <platform>
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
Sign up for a [youtube developer account](https://developers.google.com/youtube/)

And a [spotify developer account](https://developer.spotify.com/)

Add the client keys/secrets to your `dev.env` file.

```
dev.env

NGROK_URI = <ngrok_url>

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
Give it a `docker-compose restart` and you should be good to go!

Happy slacktuning!