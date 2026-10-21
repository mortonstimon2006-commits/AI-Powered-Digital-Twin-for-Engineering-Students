---
title: How the AI Career Guidance App uses and protects your data
---

# How the AI Career Guidance App uses and protects your data

## What is stored

The AI Career Guidance App stores the profile information you enter (academic details, skills, projects, experience, certifications, goals), assessment results recorded by mentors, versioned snapshots of your twin, readiness estimates, roadmaps, simulations you save, documents you upload, and your mentor conversations. Attendance is stored only if you grant the attendance-data consent.

## What is not collected

The AI Career Guidance App does not ask for, and does not use, protected personal attributes such as gender, religion, caste or date of birth. These attributes are never inputs to any model.

## Local AI

The Personalized Mentor and the document embeddings run on a local model through Ollama. Your prompts, profile and documents are not sent to external AI services.

## Who can see your data

- You can see everything stored about you.
- A mentor can view your twin only if an administrator has assigned them to you **and** you have granted the mentor-sharing consent. You can withdraw this consent at any time.
- Administrators manage the catalogue and the system. Sensitive administrative actions are recorded in an audit log.

## Your controls

From Privacy settings you can:

- grant or withdraw optional consents (mentor sharing, research use, attendance data);
- export all of your data as a JSON file;
- delete your account, which permanently removes your profile, documents, conversations and derived data.

## Retention

Uploaded documents and mentor conversations are deleted automatically after the retention period configured by your institution. Expired sessions and one-time tokens are purged regularly.

## Research use

If you grant the research-use consent, assessor labels recorded about you, together with the frozen profile snapshot they refer to, may be used to train and evaluate future versions of the readiness model. Without that consent, your data is never used for training.
