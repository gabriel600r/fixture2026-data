# Privacy Policy — Fixture Fútbol: Ligas En Vivo

**Last updated:** October 3, 2026

**Developer:** EgeaINC (Gabriel Egea)

## Introduction

Fixture Fútbol ("the App", formerly Fixture Mundial 2026) shows live scores, fixtures, tables, brackets and match details for football leagues and cups. All of its features are free. The App is supported by ads; the optional **PRO** subscription removes them and adds a couple of extras (a nickname on the supporters' wall and one saved simulation per competition).

This Privacy Policy explains what information the App handles, who receives it, and the choices you have.

## No Account, No Sign-Up

The App has no user accounts. It does not ask for your name, email address, phone number or any other contact details.

## Information Stored on Your Device

The App stores the following **only on your device** (Android SharedPreferences and local files):

- **Preferences:** the competitions you follow, your favorite teams, language, country (for TV channels), theme and notification settings.
- **Your simulations:** the results you enter in the table and cup simulators.
- **Widget data:** the matches shown in the home screen widget.
- **Usage counters:** how many times the App has been opened, used only to decide when to show the rating and support prompts.

This data is not sent to EgeaINC. It is deleted when you clear the App's data or uninstall the App.

## Network Requests

The App connects to the internet for the following:

1. **Match data.** Scores, fixtures, tables and news are downloaded from EgeaINC's feed (`feed.egeainc.cc`, served through Cloudflare). These are read-only requests and carry no personal data. As with any web request, the servers see your IP address; it is used only to deliver the content and to protect the service.
2. **Notifications.** Goal and match alerts are delivered through **Firebase Cloud Messaging** (Google). To receive them, the App subscribes your device to topics such as a team, a competition and your language. Firebase assigns your installation an identifier in order to deliver messages. EgeaINC does not receive or store that identifier, and topics contain no personal data.
3. **Ads** (not for PRO subscribers), as described below.
4. **In-app purchases.** The PRO subscription and other purchases are processed by **Google Play Billing**. EgeaINC never sees your payment details.
5. **Supporters' wall (optional).** If you are a PRO subscriber and choose to put a nickname on the in-app wall, the App sends that nickname, together with the purchase receipt signed by Google Play, to EgeaINC's server (`muro.egeainc.cc`). The server checks Google's signature and publishes the nickname, which anyone using the App can see. You can remove your nickname at any time from the App. Nothing is sent unless you choose to publish a nickname.
6. **World Cup 2026 prediction groups (Prode).** If you created or joined a prediction group during the 2026 World Cup, the App stored the group name, your nickname and your predictions in **Firebase Realtime Database** (Google), linked to an anonymous identifier created by **Firebase Authentication**, so that group members could see each other's table. No name, email or phone number was ever requested.
7. **Ratings and updates.** The App uses Google Play's In-App Review and In-App Updates features. They are handled by Google Play.

## Advertising

The App shows ads provided by **Google AdMob**: native ads between the day's matches and a medium rectangle in the match screen. Ads are always labeled as ads, never cover a match and never open full screen. **PRO subscribers do not see ads, and the App does not request ads for them.**

To show and measure ads, Google AdMob may collect and process:

- The device's advertising ID
- Approximate location derived from the IP address
- Device and app information (model, operating system, language, app version)
- Ad interactions (impressions and taps)

This data is collected and processed by Google under its own policies, not by EgeaINC.

- How Google uses information from apps that use its services: https://policies.google.com/technologies/partner-sites
- Google Privacy Policy: https://policies.google.com/privacy

**Your choices:**

- You can reset or delete your advertising ID, or opt out of personalized ads, in your device settings (Settings → Google → Ads, or Settings → Privacy → Ads, depending on the device).
- In the European Economic Area, the United Kingdom and Switzerland, the App asks for your consent before showing personalized ads, and you can change your choice at any time in the App's Settings → **Ad privacy**.
- Subscribing to PRO removes all ads.

## Permissions

The App requests the following Android permissions:

- **Internet:** to download match data, receive notifications, load ads and process purchases.
- **Notifications:** to show goal, kick-off and full-time alerts.
- **Alarms and reminders / run at startup:** to schedule match reminders and keep them after the phone restarts.
- **Foreground service (data sync):** to keep the score of a live match updated in the notification bar while your team plays.
- **Advertising ID:** used by Google AdMob to show ads, as described above.

## Sharing

When you share a match, a table or a simulation, the App uses Android's share menu. You choose the app and the recipient; EgeaINC does not see what you share.

## Children's Privacy

The App is a general-audience sports app and is not directed at children under 13. It does not knowingly collect personal information from children.

Because people of all ages follow football with it, the App asks AdMob for ads rated **G (suitable for all audiences)** only, and ads about gambling, alcohol, dating and sexual content are blocked.

## Data Retention and Deletion

- **Data on your device:** clear it in Settings → Apps → Fixture Fútbol → Storage → Clear data, or uninstall the App.
- **Your nickname on the supporters' wall:** remove it from the App at any time.
- **Notification topics:** uninstalling the App ends the subscription.
- **Anything else** (for example, a nickname in a World Cup prediction group): write to fixture@egeainc.com and we will delete it.

## Changes to This Privacy Policy

We may update this Privacy Policy from time to time. Changes will be posted on this page with an updated "Last updated" date.

## Contact

- **Email:** fixture@egeainc.com
- **Issues and suggestions:** https://github.com/gabriel600r/fixture-feedback/issues

---

*Fixture Fútbol: Ligas En Vivo — by EgeaINC*
