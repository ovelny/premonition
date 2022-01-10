import logging
from typing import Any, Dict, List, Optional, Set

from premonition import graphql


def probe_valid_fields(
    wordlist: Set, config: graphql.Config, input_document: str
) -> Set[str]:
    valid_fields = set()

    for i in range(0, len(wordlist), config.bucket_size):
        bucket = wordlist[i : i + config.bucket_size]
        document = input_document.replace("FUZZ", " ".join(bucket))

        response = graphql.post(
            config.url,
            headers=config.headers,
            json={"query": document},
            verify=config.verify,
        )
        if "errors" in response.json():
            errors = response.json()["errors"]
        else:
            return set()

        for error in errors:
            if error["extensions"]["code"] == "selectionMismatch":
                valid_fields.add(error["path"][-1])
                logging.debug(f"Found {error['path'][-1]} as a valid field.")

    return valid_fields


def probe_valid_args(
    field: str, wordlist: Set, config: graphql.Config, input_document: str
) -> Set[str]:
    valid_args = set()

    document = input_document.replace(
        "FUZZ", f"{field}({', '.join([w + ': 7' for w in wordlist])}){{lol}}"
    )

    response = graphql.post(
        config.url,
        headers=config.headers,
        json={"query": document},
        verify=config.verify,
    )
    if "errors" in response.json():
        errors = response.json()["errors"]
    else:
        return set()

    for error in errors:
        if (
            "extensions" in error
            and error["extensions"]["code"] != "argumentNotAccepted"
            and error["extensions"]["code"] != "selectionMismatch"
            and error["extensions"]["code"] != "undefinedField"
        ):
            if "arguments" in error["extensions"]:
                if isinstance(error["extensions"]["arguments"], list):
                    for arg in error["extensions"]["arguments"]:
                        valid_args.add(arg)
                elif isinstance(error["extensions"]["arguments"], str):
                    arg = error["extensions"]["arguments"]
                    if "," in arg:
                        arg = arg.split(",")
                        arg = [a.strip() for a in arg]
                        for a in arg:
                            valid_args.add(a)
                    else:
                        valid_args.add(arg)
            if "argumentName" in error["extensions"]:
                arg = error["extensions"]["argumentName"]
                valid_args.add(arg)

    return valid_args


def probe_args(
    field: str, wordlist: Set, config: graphql.Config, input_document: str
) -> Set[str]:
    valid_args = set()

    for i in range(0, len(wordlist), config.bucket_size):
        bucket = wordlist[i : i + config.bucket_size]
        valid_args |= probe_valid_args(field, bucket, config, input_document)

    return valid_args


def probe_typeref(
    documents: List[str], context: str, config: graphql.Config
) -> Optional[graphql.TypeRef]:
    typeref = None

    for document in documents:
        response = graphql.post(
            config.url,
            headers=config.headers,
            json={"query": document},
            verify=config.verify,
        )
        errors = response.json()["errors"]

        for error in errors:
            if context == "Field":
                if "extensions" in error:
                    if "typeName" in error["extensions"]:
                        typename = error["extensions"]["typeName"]
                        logging.debug(f"Found typename {typename} in field context.")
            elif context == "InputValue":
                if "extensions" in error:
                    if "typeName" in error["extensions"]:
                        typename = error["extensions"]["typeName"]
                        logging.debug(f"Found typename {typename} in field InputValue.")

            if typename:
                typename = typename.replace("!", "").replace("[", "").replace("]", "")

                if typename.endswith("Input"):
                    kind = "INPUT_OBJECT"
                elif typename in ["Int", "Float", "String", "Boolean", "ID"]:
                    kind = "SCALAR"
                else:
                    kind = "OBJECT"

                is_list = True if "[" and "]" in typename else False
                non_null_item = True if is_list and "!]" in typename else False
                non_null = True if typename.endswith("!") else False

                typeref = graphql.TypeRef(
                    name=typename,
                    kind=kind,
                    is_list=is_list,
                    non_null_item=non_null_item,
                    non_null=non_null,
                )
            else:
                logging.warning(
                    f"Unknown error message in probe_typeref with context {context}: {error['message']}"
                )

            if typeref:
                return typeref

    return None


def probe_field_type(
    field: str, config: graphql.Config, input_document: str
) -> graphql.TypeRef:
    documents = [
        input_document.replace("FUZZ", f"{field}"),
        input_document.replace("FUZZ", f"{field} {{ lol }}"),
    ]

    typeref = probe_typeref(documents, "Field", config)
    return typeref


def probe_arg_typeref(
    field: str, arg: str, config: graphql.Config, input_document: str
) -> graphql.TypeRef:
    documents = [
        input_document.replace("FUZZ", f"{field}({arg}: 7)"),
        input_document.replace("FUZZ", f"{field}({arg}: {{}})"),
        input_document.replace("FUZZ", f"{field}({arg[:-1]}: 7)"),
        input_document.replace("FUZZ", f'{field}({arg}: "7")'),
        input_document.replace("FUZZ", f"{field}({arg}: false)"),
    ]

    typeref = probe_typeref(documents, "InputValue", config)
    return typeref


def probe_typename(input_document: str, config: graphql.Config) -> str:
    typename = None
    wrong_field = "imwrongfield"
    document = input_document.replace("FUZZ", wrong_field)

    response = graphql.post(
        config.url,
        headers=config.headers,
        json={"query": document},
        verify=config.verify,
    )
    errors = response.json()["errors"]
    for error in errors:
        if error["extensions"]["code"] == "undefinedField":
            typename = error["extensions"]["typeName"]

    if typename is None:
        raise Exception("Expected typename to be found.")

    typename = typename.replace("[", "").replace("]", "").replace("!", "")

    return typename


def fetch_root_typenames(config: graphql.Config) -> Dict[str, Optional[str]]:
    documents = {
        "queryType": "query { __typename }",
        "mutationType": "mutation { __typename }",
        "subscriptionType": "subscription { __typename }",
    }
    typenames = {
        "queryType": None,
        "mutationType": None,
        "subscriptionType": None,
    }

    for name, document in documents.items():
        response = graphql.post(
            config.url,
            headers=config.headers,
            json={"query": document},
            verify=config.verify,
        )
        data = response.json().get("data", {})

        if data:
            typenames[name] = data["__typename"]

    logging.debug(f"Root typenames are: {typenames}")

    return typenames


def premonition(
    wordlist: List[str],
    config: graphql.Config,
    input_schema: Dict[str, Any] = None,
    input_document: str = None,
) -> Dict[str, Any]:
    if not input_schema:
        root_typenames = fetch_root_typenames(config)
        schema = graphql.Schema(
            queryType=root_typenames["queryType"],
            mutationType=root_typenames["mutationType"],
            subscriptionType=root_typenames["subscriptionType"],
        )
    else:
        schema = graphql.Schema(schema=input_schema)

    typename = probe_typename(input_document, config)
    logging.debug(f"__typename = {typename}")

    valid_mutation_fields = probe_valid_fields(wordlist, config, input_document)
    logging.debug(f"{typename}.fields = {valid_mutation_fields}")

    for field_name in valid_mutation_fields:
        typeref = probe_field_type(field_name, config, input_document)
        field = graphql.Field(field_name, typeref)

        if field.type.name not in ["Int", "Float", "String", "Boolean", "ID"]:
            arg_names = probe_args(field.name, wordlist, config, input_document)
            logging.debug(f"Found {typename}.{field_name}.args = {arg_names}")
            for arg_name in arg_names:
                arg_typeref = probe_arg_typeref(
                    field.name, arg_name, config, input_document
                )
                if not arg_typeref:
                    logging.warning(
                        f"Skip argument {arg_name} because TypeRef equals {arg_typeref}"
                    )
                    continue
                arg = graphql.InputValue(arg_name, arg_typeref)

                field.args.append(arg)
                schema.add_type(arg.type.name, "INPUT_OBJECT")
        else:
            logging.debug(
                f"Skip probe_args() for '{field.name}' of type '{field.type.name}'"
            )

        schema.types[typename].fields.append(field)
        schema.add_type(field.type.name, "OBJECT")

    return schema.to_json()
