# User Session Manage

## Overview

The **User Session Management** module enhances Odoo's session control by allowing administrators to set session limits and expiry configurations for individual users. With features like tracking login history, managing active sessions across devices, and enabling session restrictions, this module provides better security and control over user access and activity.

## Enabling and Configuring User Session Management
Enable Session Limit Management: Activate this to manage session limit settings.
Session Limit Configuration: Choose between a single session option One Session for all Users (default) or Based On User Configuration option.
Enable Session Expiry Management: Activate this to manage session expiration settings.
Session Expiry Configuration: Set session durations to predefined values like 1 Day, 2 Days, 7 Days, 14 Days, or Based On User Configuration.
<img src="assets/images/01_session_manage_setting_enable.png" class="img-fluid" alt="Session Manage Setting Enable" />

## Login Information
IP Address: The IP of the machine used in the last login.
Browser: Information about the browser used (e.g., Chrome, Firefox).
Timestamp: The exact date and time of the previous login.
Device Platform: The operating system of the device (e.g., Linux, Windows).
<img src="assets/images/02_login_first_browser.png" class="img-fluid" alt="Session Manage Previous Login Details" />

## Previous Login Information Across Browsers
This ensures users are always informed about their last session details IP Address, Browser, Timestamp, and Device Platform regardless of the browser or device used.
<img src="assets/images/03_login_second_browser.png" class="img-fluid" alt="Previous Login Information Across Browsers" />

## Active Session Termination
When a user logs in from a different browser, the previous session is automatically terminated. This ensures only one active session at a time, providing enhanced control and security.
<img src="assets/images/04_logout.png" class="img-fluid" alt="Active Session Termination" />

## Session Management Options
Your Session Devices displays detailed information about active sessions and devices. Your Login History shows a list of users and their login times.
<img src="assets/images/05_two_options.png" class="img-fluid" alt="Session Management Options" />

## Your Session Devices Details
This option shows detailed information about your active sessions. This includes the user, the IP address of the device, the timestamp for the first and last activities, the device platform (e.g., Linux, Windows), and the browser being used (e.g., Chrome, Firefox). Additionally, there's a Logout button, which allows you to log out directly from that specific device or browser session. This feature gives users easy access to monitor and manage their active sessions for better security control.
<img src="assets/images/06_total_sessions.png" class="img-fluid" alt="Your Session Devices Details" />

## Your Login History Details
This displays a list of all logins, showing the user and their corresponding login time. This feature allows users to quickly track their login activity and provides a clear overview of when each user accessed the system.
<img src="assets/images/07_session_history.png" class="img-fluid" alt="Your Login History Details" />

## Session Limit and Expiry Configuration
In this, both Session Limit Configuration and Session Expiry Configuration are set to User-Based. This means that the session limits and expiry durations can be configured individually for each user, allowing for more personalized control over their sessions and login behavior.
<img src="assets/images/08_user_based_options.png" class="img-fluid" alt="Your Login History Details" />

## Configuring Session Limit and Expiry By User Prefrecnce
You can go to user's Preferences to set the Session Limit Count and Session Expiry. Here, you can enter valid values for the maximum number of sessions allowed per user and define the session expiry duration in hours. This provides personalized session management for each user.
<img src="assets/images/09_user_based_options_selection.png" class="img-fluid" alt="Configuring Session Limit and Expiry By User Prefrecnce" />
