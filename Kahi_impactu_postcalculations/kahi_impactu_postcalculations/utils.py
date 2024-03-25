from pymongo import MongoClient
from math import log, exp
from spacy import load

en_model = load('en_core_web_sm')
es_model = load('es_core_news_sm')
stopwords = en_model.Defaults.stop_words.union(es_model.Defaults.stop_words)


# Global variables required for multiprocessing
# thread lock are not serializable, this makes pymongo "fork safe"
# Database to read the data (kahi output with works, person and affiliations)
db = None
impactu_db = None  # Database to store the networks and top words
client = None
impactu_client = None


def start_mongo_client(mongodb_url, database_name, impactu_database_url, impactu_database_name):
    """
    Start the MongoDB client and select the database to use.

    Parameters:
    ----------
    mongodb_url : str
        URL of the MongoDB database.
    database_name : str
        Name of the database to use.
    impactu_database_url : str
        URL of the Impactu database.
    impactu_database_name : str
        Name of the Impactu database.
    """
    global db
    global impactu_db
    global client
    global impactu_client

    client = MongoClient(mongodb_url)
    db = client[database_name]
    impactu_client = MongoClient(impactu_database_url)
    impactu_db = impactu_client[impactu_database_name]


def count_works_one(author_id):
    """
    Count the number of works for an author.

    Parameters:
    ----------
    author : dict
        Author information.

    Returns:
        str: The author identifier.
    """
    count = db["works"].count_documents({"authors.id": author_id})
    if count != 0:
        return author_id


def network_creation(idx, collection_type, author_count):
    """
    Create a co-authorship network for an affiliation or person.

    Parameters:
    ----------
    idx : str
        Identifier of the affiliation or person.
    collection_type : str
        Type of the collection ("affiliations" or "person").
    author_count : int
        Maximum number of authors in a work.
    author_count : int
        Maximum number of authors in a work.
    db : pymongo.database.Database
        Database to extract the information.(kahi output)
    impactu_db : pymongo.database.Database
        Database to store the networks.
    """
    global db
    global impactu_db
    already = impactu_db[collection_type].find_one({"_id": idx})
    if already:
        return None

    if collection_type == "affiliations":
        aff_info = db["affiliations"].find_one({"_id": idx})
        name = aff_info["names"][0]["name"]
        for n in aff_info["names"]:
            if n["lang"] in ["es", "en"]:
                name = n["name"]
                break
        authors_key = "authors.affiliations.id"
    elif collection_type == "person":
        aff_info = db["person"].find_one({"_id": idx})
        name = aff_info["full_name"]
        authors_key = "authors.id"

    nodes = [idx]
    nodes_labels = [name]
    edges = []
    edges_coauthorships = {}
    works_count = 0

    for work in db["works"].find({authors_key: idx, "author_count": {"$lte": author_count}}):
        works_count += 1
        work_nodes = [idx]
        work_edges = []

        if collection_type == "affiliations":
            for author in work["authors"]:
                for aff in author["affiliations"]:
                    if not aff["id"]:
                        continue
                    if aff["id"] == "":
                        continue
                    if aff["id"] == idx:
                        continue
                    if not aff["id"] in nodes:
                        nodes.append(aff["id"])
                        name = aff["name"]
                        nodes_labels.append(name)
                    if not aff["id"] in work_nodes:
                        for node in work_nodes:
                            edge_found = False
                            if (idx, aff["id"]) in work_edges:
                                edge_found = True
                            elif (aff["id"], idx) in edges:
                                edge_found = True
                            if edge_found is False:
                                work_edges.append((idx, aff["id"]))
                        work_nodes.append(aff["id"])

        elif collection_type == "person":
            for author in work["authors"]:
                if not author["id"]:
                    continue
                if author["id"] == "":
                    continue
                if author["id"] == idx:
                    continue
                if not author["id"] in nodes:
                    nodes.append(author["id"])
                    name = author["full_name"]
                    nodes_labels.append(name)
                if not author["id"] in work_nodes:
                    for node in work_nodes:
                        edge_found = False
                        if (idx, author["id"]) in work_edges:
                            edge_found = True
                        elif (author["id"], idx) in edges:
                            edge_found = True
                        if edge_found is False:
                            work_edges.append((idx, author["id"]))
                    work_nodes.append(author["id"])

        # Connecting all the nodes in the work among them
        for node in work_nodes:
            if node not in nodes:
                nodes.append(node)
        for node_a, node_b in work_edges:
            edge_found = (node_a, node_b) in edges or (
                node_b, node_a) in edges
            if not edge_found:
                edges_coauthorships[str(
                    node_a) + str(node_b)] = edges_coauthorships.get(str(node_a) + str(node_b), 0) + 1
                edges.append((node_a, node_b))

    # Adding the connections between the coauthoring institutions
    for node in nodes:
        if node == idx:
            continue
        for work in db["works"].find({"$and": [{authors_key: node}, {authors_key: {"$ne": idx}}], "author_count": {"$lte": author_count}}):
            if collection_type == "affiliations":
                for author in work["authors"]:
                    for aff in author["affiliations"]:
                        if aff["id"] == idx:
                            print("Problem found with affiliation id")
                            continue
                        if not aff["id"] in nodes:
                            continue
                        if node == aff["id"]:
                            continue
                        if (node, aff["id"]) in edges:
                            edges_coauthorships[str(
                                node) + str(aff["id"])] += 1
                        elif (aff["id"], node) in edges:
                            edges_coauthorships[str(
                                aff["id"]) + str(node)] += 1
                        else:
                            edges_coauthorships[str(
                                node) + str(aff["id"])] = 1
                            edges.append((node, aff["id"]))

            elif collection_type == "person":
                for author in work["authors"]:
                    if author["id"] == idx:
                        print("Problem found with author id")
                        continue
                    if not author["id"] in nodes:
                        continue
                    if node == author["id"]:
                        continue
                    if (node, author["id"]) in edges:
                        edges_coauthorships[str(
                            node) + str(author["id"])] += 1
                    elif (author["id"], node) in edges:
                        edges_coauthorships[str(
                            author["id"]) + str(node)] += 1
                    else:
                        edges_coauthorships[str(
                            node) + str(author["id"])] = 1
                        edges.append((node, author["id"]))

    # Constructing the actual format to insert in the database
    num_nodes = len(nodes)
    nodes_db = [
        {
            "id": str(node),
            "label": nodes_labels[nodes.index(node)],
            "degree": len([(i, j) for i, j in edges if i == node or j == node]),
            "size": 50 * log(1 + len([(i, j) for i, j in edges if i == node or j == node]) / (num_nodes - 1), 2) if num_nodes > 1 else 1
        } for node in nodes]
    edges_db = [
        {
            "source": str(node_a),
            "sourceName": nodes_labels[nodes.index(node_a)],
            "target": str(node_b),
            "targetName": nodes_labels[nodes.index(node_b)],
            "coauthorships": edges_coauthorships.get(str(node_a) + str(node_b), 0),
            "size": edges_coauthorships.get(str(node_a) + str(node_b), 0)
        } for node_a, node_b in edges
    ]

    top = max([e["coauthorships"] for e in edges_db]) if edges_db else 1
    bot = min([e["coauthorships"] for e in edges_db]) if edges_db else 1
    for edge in edges_db:
        if abs(top - edge["coauthorships"]) < 0.01:
            edge["size"] = 10
        elif abs(bot - edge["coauthorships"]) < 0.01:
            edge["size"] = 1
        else:
            size = 10 / (1 + exp(6 - 10 * edge["coauthorships"] / top))
            edge["size"] = size if size >= 1 else 1
    try:
        impactu_db[collection_type].insert_one({
            "_id": idx,
            "coauthorship_network": {
                "nodes": nodes_db,
                "edges": edges_db
            }
        })
    except Exception as e:
        print(e)
        print(f"ERROR: too big network for id {idx}")


def top_words(collection, aff, authors_key):
    """
    Extract the top words for a given collection (affiliations or person).

    Parameters:
    ----------
    collection : str
        Type of the collection ("affiliations" or "person").
    """
    global db
    global impactu_db
    global client
    global es_model
    global en_model
    global stopwords

    aff_db = impactu_db[collection].find_one(
        {"_id": aff, "top_words": {"$exists": 1}})
    if aff_db:
        if collection == "person":
            return
    results = {}

    for work in db["works"].find({authors_key: aff, "titles.title": {"$exists": 1}}, {"titles": 1}):
        title = work["titles"][0]["title"].lower()
        lang = work["titles"][0]["lang"]

        model = es_model if lang == "es" else en_model

        title = model(title)

        for token in title:
            if token.lemma_.isnumeric():
                continue
            if token.lemma_ in stopwords:
                continue
            if len(token.lemma_) < 4:
                continue
            if token.lemma_ in results.keys():
                results[token.lemma_] += 1
            else:
                results[token.lemma_] = 1

    topN = sorted(results.items(),
                  key=lambda x: x[1], reverse=True)[:20]
    results = [{"name": top[0], "value": top[1]} for top in topN]
    aff_db = impactu_db[collection].find_one({"_id": aff})
    if aff_db:
        impactu_db[collection].update_one(
            {"_id": aff}, {"$set": {"top_words": results}})
    else:
        impactu_db[collection].insert_one(
            {"_id": aff, "top_words": results})
