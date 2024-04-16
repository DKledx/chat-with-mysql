# Standard library imports
from dotenv import load_dotenv

# Related third party imports
from langchain_core.messages import AIMessage, HumanMessage
from langchain_community.utilities import SQLDatabase

import streamlit as st

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from langchain_openai import ChatOpenAI



# =======================================================================================================

def init_database(user: str, password: str, host: str, port: str, database: str) -> SQLDatabase:
    """
    Initialize a SQLDatabase object with the given credentials
    """
    db_uri = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    return SQLDatabase.from_uri(db_uri)


def get_sql_chain(db):
    """
    Returns a proper SQL query for interacting with a user who is asking questions about a company's database.

    Args:
        db: An instance of the database connection.

    Returns:
        A SQL chain for answering user's questions based on the conversation history and table schema.

    """
    
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into account.

    <SCHEMA>{schema}</SCHEMA>

    Conversation History: {chat_history}

    Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even backticks.

    For example:
    Question: which 3 artists have the most tracks?
    SQL Query: SELECT ArtistId, COUNT(*) as track_count FROM Track GROUP BY ArtistId ORDER BY track_count DESC LIMIT 3;
    Question: Name 10 artists
    SQL Query: SELECT Name FROM Artist LIMIT 10;

    Your turn:

    Question: {question}
    SQL Query:
    """

    prompt = ChatPromptTemplate.from_template(template) # Create a prompt template

    llm = ChatOpenAI(model="gpt-4-0125-preview")
                           
    def get_schema(_):
        return db.get_table_info()
    return (
        RunnablePassthrough.assign(schema=get_schema) 
        | prompt
        | llm
        | StrOutputParser() 
    )


def get_response(user_query: str, db: SQLDatabase, chat_history: list):
    """
    Returns a natural language response to a user's question based on the conversation history and table schema.

    Parameters:
    - user_query (str): The user's question.
    - db (SQLDatabase): The database object containing the table schema and query execution methods.
    - chat_history (list): The conversation history.

    Returns:
    - str: The natural language response to the user's question.
    """

    sql_chain = get_sql_chain(db) 

    template = """
        You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
        Based on the table schema below, question, sql query, and sql response, write a natural language reponse.
        <SCHEMA>{schema}</SCHEMA>

        Conversation History: {chat_history}
        SQL Query: <SQL>{query}</SQL>
        Question: {question}
        SQL Response: {response}

    """
    prompt = ChatPromptTemplate.from_template(template)

    llm = ChatOpenAI(model="gpt-4-0125-preview")

    chain = (
        RunnablePassthrough.assign(query=sql_chain).assign(
            schema=lambda _: db.get_table_info(),
            response=lambda _: db.run(_["query"]),
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain.invoke({
        "question": user_query,
        "chat_history": chat_history,
    })


#=======================================================================================================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        AIMessage("Hello! I am a SQL assistant. Ask me anything about your Database."),
    ]

load_dotenv()

st.set_page_config(page_title="Chat with MySQL", page_icon=":speech_balloon:")  

st.title("Chat with MySQL")

with st.sidebar:
    st.subheader("Setting")
    st.write("This is a chat application with MySQL. Coonect to the database and start chatting.")

    st.text_input("Host", value="localhost", key="host")
    st.text_input("Port", value="3306", key="port")
    st.text_input("User", value="root", key="user")
    st.text_input("Password", type="password", value="", key="password")
    st.text_input("Database", value="Chinook", key="database")

    if st.button("Connect"):
        with st.spinner("Connecting to the database..."):
            db = init_database(
                st.session_state["user"],
                st.session_state["password"],
                st.session_state["host"],
                st.session_state["port"],
                st.session_state["database"]
            )
            st.session_state.db = db
            st.success("Connected to the database.")


for message in st.session_state.chat_history:
    if isinstance(message, AIMessage):
      with st.chat_message("Ai"):
         st.markdown(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)


user_query = st.chat_input("Type your message here...")
if user_query is not None and user_query.strip() != "":
    st.session_state.chat_history.append(HumanMessage(content=user_query))


    with st.chat_message("HUman"):
        st.markdown(user_query)

    with st.chat_message("AI"):
        response = get_response(user_query, st.session_state.db, st.session_state.chat_history)
        st.markdown(response)

    st.session_state.chat_history.append(AIMessage(content=response))




           

                  

