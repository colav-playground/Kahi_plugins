from kahi_scienti_works.parser import parse_scienti
from kahi_impactu_utils.Utils import lang_poll, doi_processor, compare_author
import re
from time import time
from bson import ObjectId


def get_doi(reg):
    for i in reg["external_ids"]:
        if i["source"] == 'doi':
            return i["id"]
    return False


def process_one_update(scienti_reg, colav_reg, db, collection, empty_work, verbose=0):
    """
    Method to update a register in the kahi database from scholar database if it is found.
    This means that the register is already on the kahi database and it is being updated with new information.


    Parameters
    ----------
    scienti_reg : dict
        Register from the scienti database
    colav_reg : dict
        Register from the colav database (kahi database for impactu)
    db: pymongo.collection.Collection
        Database where ETL result is stored
    collection : pymongo.collection.Collection
        Collection in the database where the register is stored (Collection of works)
    empty_work : dict
        Empty dictionary with the structure of a register in the database
    verbose : int, optional
        Verbosity level. The default is 0.
    """
    entry = parse_scienti(
        scienti_reg, empty_work.copy(), verbose=verbose)
    # updated
    for upd in colav_reg["updated"]:
        if upd["source"] == "scienti":
            # scienti groups
            if "group" in scienti_reg.keys():
                for group in scienti_reg["group"]:
                    group_reg = db["affiliations"].find_one(
                        {"external_ids.id": group["COD_ID_GRUPO"]})
                    if group_reg is None:
                        group_reg = db["affiliations"].find_one(
                            {"external_ids.id": group["NRO_ID_GRUPO"]})
                    if group_reg:
                        found = False
                        for rgroup in colav_reg["groups"]:
                            if group_reg["_id"] == rgroup["id"]:
                                found = True
                                break
                        if not found:
                            colav_reg["groups"].append(
                                {"id": group_reg["_id"], "name": group_reg["names"][0]["name"]})
                    if not group_reg:
                        print(
                            f'WARNING: group with ids {scienti_reg["group"]["COD_ID_GRUPO"]} and {scienti_reg["group"]["NRO_ID_GRUPO"]} not found in affiliation')

            # authors
            if "openalex" in [upd["source"] for upd in colav_reg["updated"]]:
                # añadir comparacion de autores
                continue
                # return None
            author = entry["authors"][0]
            author_db = None
            for ext in author["external_ids"]:
                author_db = db["person"].find_one(
                    {"external_ids.id": ext["id"]})
                if author_db:
                    break
            if author_db:
                improve_author = False
                found = False
                for a in colav_reg["authors"]:
                    if author_db["_id"] == a["id"]:
                        found = True
                        if a["affiliations"] == []:
                            improve_author = True
                            collection.update_one(
                                {"_id": colav_reg["_id"]},
                                {"$pull": {"authors": {"id": a["id"]}}, "$inc": {
                                    "author_count": -1}}
                            )
                if found and not improve_author:
                    return None
                sources = [ext["source"]
                           for ext in author_db["external_ids"]]
                ids = [ext["id"]
                       for ext in author_db["external_ids"]]
                for ext in author["external_ids"]:
                    if ext["id"] not in ids:
                        author_db["external_ids"].append(ext)
                        sources.append(ext["source"])
                        ids.append(ext["id"])
                author = {
                    "id": author_db["_id"],
                    "full_name": author_db["full_name"],
                    "affiliations": author["affiliations"]
                }
            else:
                author_db = db["person"].find_one(
                    {"full_name": author["full_name"]})
                if author_db:
                    sources = [ext["source"]
                               for ext in author_db["external_ids"]]
                    ids = [ext["id"]
                           for ext in author_db["external_ids"]]
                    for ext in author["external_ids"]:
                        if ext["id"] not in ids:
                            author_db["external_ids"].append(ext)
                            sources.append(ext["source"])
                            ids.append(ext["id"])
                    author = {
                        "id": author_db["_id"],
                        "full_name": author_db["full_name"],
                        "affiliations": author["affiliations"]
                    }
                else:
                    author = {
                        "id": "",
                        "full_name": author["full_name"],
                        "affiliations": author["affiliations"]
                    }
            for j, aff in enumerate(author["affiliations"]):
                aff_db = None
                if "external_ids" in aff.keys():
                    for ext in aff["external_ids"]:
                        aff_db = db["affiliations"].find_one(
                            {"external_ids.id": ext["id"]})
                        if aff_db:
                            break
                if aff_db:
                    name = aff_db["names"][0]["name"]
                    for n in aff_db["names"]:
                        if n["source"] == "ror":
                            name = n["name"]
                            break
                        if n["lang"] == "en":
                            name = n["name"]
                        if n["lang"] == "es":
                            name = n["name"]
                    author["affiliations"][j] = {
                        "id": aff_db["_id"],
                        "name": name,
                        "types": aff_db["types"]
                    }
                else:
                    aff_db = db["affiliations"].find_one(
                        {"names.name": aff["name"]})
                    if aff_db:
                        name = aff_db["names"][0]["name"]
                        for n in aff_db["names"]:
                            if n["source"] == "ror":
                                name = n["name"]
                                break
                            if n["lang"] == "en":
                                name = n["name"]
                            if n["lang"] == "es":
                                name = n["name"]
                        author["affiliations"][j] = {
                            "id": aff_db["_id"],
                            "name": name,
                            "types": aff_db["types"]
                        }
                    else:
                        author["affiliations"][j] = {
                            "id": "",
                            "name": aff["name"],
                            "types": []
                        }
            collection.update_one(
                {"_id": colav_reg["_id"]},
                {"$push": {"authors": author}, "$inc": {
                    "author_count": 1}, "$set": {"groups": colav_reg["groups"]}}
            )

    colav_reg["updated"].append(
        {"source": "scienti", "time": int(time())})
    # titles
    if 'scienti' not in [title['source'] for title in colav_reg["titles"]]:
        lang = lang_poll(entry["titles"][0]["title"])
        colav_reg["titles"].append(
            {"title": entry["titles"][0]["title"], "lang": lang, "source": "scienti"})
    # external_ids
    ext_ids = [ext["id"] for ext in colav_reg["external_ids"]]
    for ext in entry["external_ids"]:
        if ext["id"] not in ext_ids:
            colav_reg["external_ids"].append(ext)
            ext_ids.append(ext["id"])
    # types
    for rec in entry["types"]:
        if rec not in colav_reg["types"]:
            colav_reg["types"].append(rec)

    # external urls
    url_sources = [url["source"]
                   for url in colav_reg["external_urls"]]
    for ext in entry["external_urls"]:
        if ext["source"] not in url_sources:
            colav_reg["external_urls"].append(ext)
            url_sources.append(ext["source"])

    # scienti author
    scienti_author = entry['authors'][0]
    if scienti_author:
        author_db = None
        if 'external_ids' in scienti_author.keys():
            author_ids = scienti_author['external_ids']
            author_db = db['person'].find_one(
                {'external_ids': {'$elemMatch': {'$or': author_ids}}})

        if author_db:
            name_match = None
            affiliation_match = None
            for i, author in enumerate(colav_reg['authors']):
                if author['id'] == author_db['_id']:
                    continue
                name_match = compare_author(
                    author['id'], author['full_name'], author_db['full_name'])
                doi1 = get_doi(entry)
                doi2 = get_doi(colav_reg)
                if doi1 and doi2:
                    if doi1 == doi2:
                        affiliation_match = True
                else:
                    if author['affiliations']:
                        affiliations_person = [str(aff['id'])
                                               for aff in author_db['affiliations']]
                        author_affiliations = [str(aff['id'])
                                               for aff in author['affiliations']]
                        affiliation_match = any(
                            affil in author_affiliations for affil in affiliations_person)

                if name_match and affiliation_match:
                    # replace the author, maybe add the openalex id to the record in the future
                    for reg in author_db["affiliations"]:
                        reg.pop('start_date')
                        reg.pop('end_date')

                    colav_reg["authors"][i] = {
                        "id": author_db["_id"],
                        "full_name": author_db["full_name"],
                        "affiliations": author["affiliations"]
                    }
                    break
    # the first author is the original one always (already inserted)
    if "author_others" in scienti_reg.keys():
        for i, author in enumerate(scienti_reg["author_others"][1:]):
            if author["COD_RH_REF"]:
                author_db = db["person"].find_one(
                    {"external_ids.id.COD_RH": author["COD_RH_REF"]})
                if author_db:
                    found = False
                    for author_rec in colav_reg["authors"]:
                        if author_db["_id"] == author_rec["id"]:
                            found = True
                        else:
                            # only the name can be compared, because we dont have the affiliation of the author from the paper in author_others
                            name_match = compare_author(
                                author_rec['id'], author_rec['full_name'], author_db['full_name'])
                            if name_match:
                                found = True
                                author_rec["id"] = author_db["_id"]
                                author_rec["full_name"] = author_db['full_name']
                    if not found:
                        rec = {"id": author_db["_id"],
                               "full_name": author_db["full_name"],
                               # we dont have affiliation of the author from the paper, we can´t assume one.
                               "affiliations": []
                               }
                        colav_reg["authors"].append(rec)

    # scienti groups
    if "group" in scienti_reg.keys():
        for group in scienti_reg["group"]:
            group_reg = db["affiliations"].find_one(
                {"external_ids.id": group["COD_ID_GRUPO"]})
            if group_reg is None:
                group_reg = db["affiliations"].find_one(
                    {"external_ids.id": group["NRO_ID_GRUPO"]})
            if group_reg:
                found = False
                for rgroup in colav_reg["groups"]:
                    if group_reg["_id"] == rgroup["id"]:
                        found = True
                        break
                if not found:
                    colav_reg["groups"].append(
                        {"id": group_reg["_id"], "name": group_reg["names"][0]["name"]})
            if not group_reg:
                print(
                    f'WARNING: group with ids {scienti_reg["group"]["COD_ID_GRUPO"]} and {scienti_reg["group"]["NRO_ID_GRUPO"]} not found in affiliation')
    collection.update_one(
        {"_id": colav_reg["_id"]},
        {"$set": {
            "updated": colav_reg["updated"],
            "titles": colav_reg["titles"],
            "external_ids": colav_reg["external_ids"],
            "types": colav_reg["types"],
            "bibliographic_info": colav_reg["bibliographic_info"],
            "external_urls": colav_reg["external_urls"],
            "authors": colav_reg["authors"],
            "subjects": colav_reg["subjects"],
            "groups": colav_reg["groups"]
        }}
    )


def process_one_insert(scienti_reg, db, collection, empty_work, es_handler, doi=None, verbose=0):
    """
    Function to insert a new register in the database if it is not found in the colav(kahi works) database.
    This means that the register is not on the database and it is being inserted.

    For similarity purposes, the register is also inserted in the elasticsearch index,
    all the elastic search fields are filled with the information from the register and it is
    handled by Mohan's Similarity class.

    The register is also linked to the source of the register, and the authors and affiliations are searched in the database.

    Parameters
    ----------
    scienti_reg : dict
        Register from the scienti database
    db : pymongo.database.Database
        Database where the colav collections are stored, used to search for authors and affiliations.
    collection : pymongo.collection.Collection
        Collection in the database where the register is stored (Collection of works)
    empty_work : dict
        Empty dictionary with the structure of a register in the database
    es_handler : Similarity
        Elasticsearch handler to insert the register in the elasticsearch index, Mohan's Similarity class.
    verbose : int, optional
        Verbosity level. The default is 0.
    """
    # parse
    entry = parse_scienti(scienti_reg, empty_work.copy(), doi)
    # link
    source_db = None
    if "external_ids" in entry["source"].keys():
        for ext in entry["source"]["external_ids"]:
            source_db = db["sources"].find_one(
                {"external_ids.id": ext["id"]})
            if source_db:
                break
    if source_db:
        name = source_db["names"][0]["name"]
        for n in source_db["names"]:
            if n["lang"] == "es":
                name = n["name"]
                break
            if n["lang"] == "en":
                name = n["name"]
        entry["source"] = {
            "id": source_db["_id"],
            "name": name
        }
    else:
        if "external_ids" in entry["source"].keys():
            if len(entry["source"]["external_ids"]) == 0:
                if verbose > 4:
                    if "title" in entry["source"].keys():
                        print(
                            f'Register with RH: {scienti_reg["COD_RH"]} and COD_PROD: {scienti_reg["COD_PRODUCTO"]} could not be linked to a source with name: {entry["source"]["title"]}')
                    else:
                        print(
                            f'Register with RH: {scienti_reg["COD_RH"]} and COD_PROD: {scienti_reg["COD_PRODUCTO"]} does not provide a source')
            else:
                if verbose > 4:
                    print(
                        f'Register with RH: {scienti_reg["COD_RH"]} and COD_PROD: {scienti_reg["COD_PRODUCTO"]} could not be linked to a source with {entry["source"]["external_ids"][0]["source"]}: {entry["source"]["external_ids"][0]["id"]}')  # noqa: E501
        else:
            if "title" in entry["source"].keys():
                if entry["source"]["title"] == "":
                    if verbose > 4:
                        print(
                            f'Register with RH: {scienti_reg["COD_RH"]} and COD_PROD: {scienti_reg["COD_PRODUCTO"]} does not provide a source')
                else:
                    if verbose > 4:
                        print(
                            f'Register with RH: {scienti_reg["COD_RH"]} and COD_PROD: {scienti_reg["COD_PRODUCTO"]} could not be linked to a source with name: {entry["source"]["title"]}')
            else:
                if verbose > 4:
                    print(
                        f'Register with RH: {scienti_reg["COD_RH"]} and COD_PROD: {scienti_reg["COD_PRODUCTO"]} could not be linked to a source (no ids and no name)')

        entry["source"] = {
            "id": "",
            "name": entry["source"]["title"] if "title" in entry["source"].keys() else ""
        }

    author = entry["authors"][0]
    # search authors and affiliations in db
    author_db = None
    for ext in author["external_ids"]:
        author_db = db["person"].find_one(
            {"external_ids.id": ext["id"]})
        if author_db:
            break
    if author_db:
        sources = [ext["source"]
                   for ext in author_db["external_ids"]]
        ids = [ext["id"] for ext in author_db["external_ids"]]
        for ext in author["external_ids"]:
            if ext["id"] not in ids:
                author_db["external_ids"].append(ext)
                sources.append(ext["source"])
                ids.append(ext["id"])
        author = {
            "id": author_db["_id"],
            "full_name": author_db["full_name"],
            "affiliations": author["affiliations"]
        }
    else:
        author_db = db["person"].find_one(
            {"full_name": author["full_name"]})
        if author_db:
            sources = [ext["source"]
                       for ext in author_db["external_ids"]]
            ids = [ext["id"] for ext in author_db["external_ids"]]
            for ext in author["external_ids"]:
                if ext["id"] not in ids:
                    author_db["external_ids"].append(ext)
                    sources.append(ext["source"])
                    ids.append(ext["id"])
            author = {
                "id": author_db["_id"],
                "full_name": author_db["full_name"],
                "affiliations": author["affiliations"]
            }
        else:
            author = {
                "id": "",
                "full_name": author["full_name"],
                "affiliations": author["affiliations"]
            }
    for j, aff in enumerate(author["affiliations"]):
        aff_db = None
        if "external_ids" in aff.keys():
            for ext in aff["external_ids"]:
                aff_db = db["affiliations"].find_one(
                    {"external_ids.id": ext["id"]})
                if aff_db:
                    break
        if aff_db:
            name = aff_db["names"][0]["name"]
            for n in aff_db["names"]:
                if n["source"] == "ror":
                    name = n["name"]
                    break
                if n["lang"] == "en":
                    name = n["name"]
                if n["lang"] == "es":
                    name = n["name"]
            author["affiliations"][j] = {
                "id": aff_db["_id"],
                "name": name,
                "types": aff_db["types"]
            }
        else:
            aff_db = db["affiliations"].find_one(
                {"names.name": aff["name"]})
            if aff_db:
                name = aff_db["names"][0]["name"]
                for n in aff_db["names"]:
                    if n["source"] == "ror":
                        name = n["name"]
                        break
                    if n["lang"] == "en":
                        name = n["name"]
                    if n["lang"] == "es":
                        name = n["name"]
                author["affiliations"][j] = {
                    "id": aff_db["_id"],
                    "name": name,
                    "types": aff_db["types"]
                }
            else:
                author["affiliations"][j] = {
                    "id": "",
                    "name": aff["name"],
                    "types": []
                }
    entry["authors"][0] = author
    # the first author is the original one always (already inserted)
    if "author_others" in scienti_reg.keys():
        for author in scienti_reg["author_others"][1:]:
            if author["COD_RH_REF"]:
                author_db = db["person"].find_one(
                    {"external_ids.id.COD_RH": author["COD_RH_REF"]})
                if author_db:
                    rec = {"id": author_db["_id"],
                           "full_name": author_db["full_name"],
                           # we dont have affiliation of the author from the paper, we can´t assume one.
                           "affiliations": []
                           }
                    entry["authors"].append(rec)

    entry["author_count"] = len(entry["authors"])
    # scienti group
    if "group" in scienti_reg.keys():
        for group in scienti_reg["group"]:
            group_reg = db["affiliations"].find_one(
                {"external_ids.id": group["COD_ID_GRUPO"]})
            if group_reg is None:
                group_reg = db["affiliations"].find_one(
                    {"external_ids.id": group["NRO_ID_GRUPO"]})
            if group_reg:
                entry["groups"].append(
                    {"id": group_reg["_id"], "name": group_reg["names"][0]["name"]})
            if not group_reg:
                print(
                    f'WARNING: group with ids {scienti_reg["group"]["COD_ID_GRUPO"]} and {scienti_reg["group"]["NRO_ID_GRUPO"]} not found in affiliation')

    # insert in mongo
    response = collection.insert_one(entry)
    # insert in elasticsearch
    if es_handler:
        work = {}
        work["title"] = entry["titles"][0]["title"]
        work["source"] = entry["source"]["name"]
        work["year"] = entry["year_published"]
        work["volume"] = entry["bibliographic_info"]["volume"] if "volume" in entry["bibliographic_info"].keys() else ""
        work["issue"] = entry["bibliographic_info"]["issue"] if "issue" in entry["bibliographic_info"].keys() else ""
        work["first_page"] = entry["bibliographic_info"]["first_page"] if "first_page" in entry["bibliographic_info"].keys() else ""
        work["last_page"] = entry["bibliographic_info"]["last_page"] if "last_page" in entry["bibliographic_info"].keys() else ""
        authors = []
        for author in entry['authors']:
            if len(authors) >= 5:
                break
            if "full_name" in author.keys():
                authors.append(author["full_name"])
        work["authors"] = authors
        work["provenance"] = "scienti"

        es_handler.insert_work(_id=str(response.inserted_id), work=work)
    else:
        if verbose > 4:
            print("No elasticsearch index provided")


def process_one(scienti_reg, db, collection, empty_work, es_handler, similarity, verbose=0):
    """
    Function to process a single register from the scienti database.
    This function is used to insert or update a register in the colav(kahi works) database.

    Parameters
    ----------
    scienti_reg : dict
        Register from the scienti database
    db : pymongo.database.Database
        Database where the colav collections are stored, used to search for authors and affiliations.
    collection : pymongo.collection.Collection
        Collection in the database where the register is stored (Collection of works)
    empty_work : dict
        Empty dictionary with the structure of a register in the database
    es_handler : Similarity
        Elasticsearch handler to insert the register in the elasticsearch index, Mohan's Similarity class.
    verbose : int, optional
        Verbosity level. The default is 0.
    """
    doi = None
    # register has doi
    if "TXT_DOI" in scienti_reg.keys():
        if scienti_reg["TXT_DOI"]:
            doi = doi_processor(scienti_reg["TXT_DOI"])
    if not doi:
        if "TXT_WEB_PRODUCTO" in scienti_reg.keys() and scienti_reg["TXT_WEB_PRODUCTO"] and "10." in scienti_reg["TXT_WEB_PRODUCTO"]:
            doi = doi_processor(scienti_reg["TXT_WEB_PRODUCTO"])
            if doi:
                extracted_doi = re.compile(
                    r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', re.IGNORECASE).match(doi)
                if extracted_doi:
                    doi = extracted_doi.group(0)
                    for keyword in ['abstract', 'homepage', 'tpmd200765', 'event_abstract']:
                        doi = doi.split(
                            f'/{keyword}')[0] if keyword in doi else doi
    if doi:
        # is the doi in colavdb?
        colav_reg = collection.find_one({"external_ids.id": doi})

        if colav_reg:  # update the register
            process_one_update(
                scienti_reg, colav_reg, db, collection, empty_work, verbose=verbose)
        else:  # insert a new register
            process_one_insert(
                scienti_reg, db, collection, empty_work, es_handler, doi, verbose=verbose)
    elif similarity:  # does not have a doi identifier
        # elasticsearch section
        if es_handler:
            # Search in elasticsearch
            entry = parse_scienti(
                scienti_reg, empty_work.copy(), verbose=verbose)
            work = {}
            work["title"] = entry["titles"][0]["title"]
            work["source"] = entry["source"]["name"] if "name" in entry["source"].keys(
            ) else ""
            work["year"] = entry["year_published"]
            work["volume"] = entry["bibliographic_info"]["volume"] if "volume" in entry["bibliographic_info"].keys() else ""
            work["issue"] = entry["bibliographic_info"]["issue"] if "issue" in entry["bibliographic_info"].keys() else ""
            work["first_page"] = entry["bibliographic_info"]["first_page"] if "first_page" in entry["bibliographic_info"].keys() else ""
            work["last_page"] = entry["bibliographic_info"]["last_page"] if "last_page" in entry["bibliographic_info"].keys() else ""
            authors = []
            for author in entry['authors']:
                if len(authors) >= 5:
                    break
                if "full_name" in author.keys():
                    authors.append(author["full_name"])
            work["authors"] = authors
            work["provenance"] = "scienti"
            response = es_handler.search_work(
                title=work["title"],
                source=work["source"],
                year=work["year"],
                authors=authors,
                volume=work["volume"],
                issue=work["issue"],
                page_start=work["first_page"],
                page_end=work["last_page"]
            )

            if response:  # register already on db... update accordingly
                colav_reg = collection.find_one(
                    {"_id": ObjectId(response["_id"])})
                if colav_reg:
                    process_one_update(scienti_reg, colav_reg, db,
                                       collection, empty_work, verbose)
                else:
                    if verbose > 4:
                        print("Register with {} not found in mongodb".format(
                            response["_id"]))
                        print(response)
            else:  # insert new register
                process_one_insert(scienti_reg, db, collection,
                                   empty_work, es_handler, verbose)
        else:
            if verbose > 4:
                print("No elasticsearch index provided")
