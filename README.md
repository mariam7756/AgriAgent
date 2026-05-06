# AgriAgent
An end-to-end implementation of a Retrieval-Augmented Generation (RAG) system that enables agricultural companies to deploy intelligent AI agents capable of answering domain-specific queries using proprietary knowledge sources.
 

# requirments 
python 3.8 or later 

## Installing python using conda 
1) download and install mini conda here https://www.anaconda.com/docs/getting-started/miniconda/install

2) create a new environment using the following command : 

```bash
conda create -n mini-rag python=3.8
```
3) activate  the invironment 
```bash
conda activate mini-rag
```
## optional setup for interface 
```bash 
export PS1="\[\033[01;32m\]\u@\h:\w\n\[\033[00m\]\$"
```

## install require packages
```bash 
$ pip install -r requirements.txt
```

## setup invironment variables
```bash
$ cp .env.example .env
```
 set your  environment varriables in the `.env` file like `OPEN_API_KEY` value  
  
  ## Docker Compose Services
  ```bash
  $ cd docker
  $ cp .env.example .env
  ```
  - update  ` .env` with your credintals

 ## Run the FastApi server 
 ```bash
 uvicorn main:app --reload --host 0.0.0.0 --port 5000
 ``` 


 ####  https://lnkd.in/dPkAN5pR   دي اكستنشن بتقلل الtokens###   

 ##  git branch     ##
 ### git add .    ###
 ### git commit -m ""  ###
 ### git push -u origin ###
 
 
## qwen2.5:3b-instruct-q3_K_S
## wp ollama run  qwen2.5:3b-instruct-q3_K_S##

