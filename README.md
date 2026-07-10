# PIHUB

Welcome to the PIHUB repository. 

PIHUB is a comprehensive educational platform that serves interactive curriculum, textbooks, and AI-driven insights to classrooms using a localized edge-node architecture.

## Architecture & Deployment

The PIHUB backend utilizes Docker and is designed to operate in a distributed environment to maximize performance while minimizing hardware requirements in the classroom.

For full deployment instructions, particularly on how to split the heavy AI services onto a central server while using a Raspberry Pi as the lightweight classroom gateway, please refer to our detailed deployment guide:

*   [**PIHUB Distributed Deployment Guide**](backend/DEPLOYMENT_GUIDE.md)

## Repository Structure
*   `/backend` - Contains the microservices architecture (API Gateway, Pack Service, Inference Service, etc.) and Docker configurations.
*   `/TEXTBOOKS` - Raw PDF library of the curriculum.
*   `/phet_downloads` - Local copies of PhET interactive simulations.
*   `/textbook_artifacts` - Generated artifacts (flashcards, summaries, chunks) extracted from the curriculum.
