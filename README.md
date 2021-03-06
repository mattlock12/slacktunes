# Slacktunes

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

Add `ngrok_url` to your `dev.env` as `BASE_URI`

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
docker-compose exec -it slacktunes_backend flask db upgrade
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

Change the `Request URL` to your `<ngrok_url>/slack_events/`

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
#### Setting up a Service User
Slacktunes uses a 'Service User' to perform searches for cross-platform adding. This is just a regular User with the `is_service_user` attribute set to `True`.

The easiest way to set up this Service User for local dev-ing is to:
1. `/create_playlist` and follow instructions to auth. This will create a User and store credentials for Youtube.
1. `/create_playlist something s` and follow instructions to add credentials for Spotify
1. `docker exec -it slacktunes_backend python -c 'from src.models import User;u = User.query.first();u.is_service_user = True;u.save()` to set your User as the Service User


#### That's it!
Give it a `docker-compose restart` and you should be good to go!

Happy slacktuning!

## NOTES:
Slacktunes is set up to use the refresh token returned from the Youtube and Spotify APIs to refresh credentials indefinitely without the need for repeated user input.

However, Youtube (at least) only sends the refresh token _the first time you request credentials_. Which means that if you update the client_secret or the api key you're using, and the old credentials (stored in the Slacktunes database) become unusable, it is _not enough_ to delete them from the database and re-auth -- because the Youtube API will recognize that this is the _second_ (or whatever) time you're authorizing access and it _will not_ return the refresh token.

The only way to get the refresh token is to:
1. Go to your Google account and de-authorized Slacktunes
1. Delete the Credential object for Youtube from the Slacktunes database
1. Go through the grant process

## Deployment Notes:
Until a better process is implemented:
1. ssh into the host
1. Manually edit `database-init-prod.sql`, `docker-compose.prod.yml`, and `prod.env` manually to override:
    - POSTGRES_PASSWORD
    - slacktunes password
    - keys and secrets in prod.env
1. `docker-compose -f docker-compose.prod.yml up -d --build`