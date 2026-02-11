# mini-rag-app
Thid is application of the RAG model to help Agricultural companies to question answering  

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
$ pip install -r reqirements.txt
```

## setup invironment variables
```bash
$ cp .env.example .env
```
 set your  environment varriables in the `.env` file like `OPEN_API_KEY` value