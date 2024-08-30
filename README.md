# Vehicle Safety and Compliance System

## Overview

The Vehicle Safety and Compliance System is a comprehensive application designed to enhance vehicle safety and compliance through Automatic Number Plate Recognition (ANPR). It allows administrators to view data, upload images, and enables state transport departments to verify vehicle number plates. The system includes functionalities for license plate detection, fine issuance, database management, and SMS notifications for fine payments.

## Features

- **Automatic Number Plate Recognition (ANPR):** Detects and reads vehicle number plates from images.
- **Administrator Dashboard:** View vehicle data, upload images, and manage system settings.
- **Verification System:** Allows state transport departments to verify vehicle number plates.
- **Fine Issuance:** Issues fines for incomplete or incorrect number plates.
- **Email Notifications:** Sends email notifications to vehicle owners regarding incomplete number plates.
- **Payment Integration:** Allows users to pay fines online.
- **SMS Notifications:** Sends SMS reminders for fine payments.

## Prerequisites

- Python 3.x
- Flask
- OpenCV
- Tesseract OCR
- A database (e.g., MySQL, MongoDB)

## Usage

- **Administrator Functions:** Log in to the admin panel to view data, upload images, and manage settings.
- **Verification:** Use the verification module to check vehicle number plates.
- **Fine Management:** Admins can issue fines and manage payments through the system.
