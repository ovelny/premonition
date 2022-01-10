# premonition

premonition is a fork of [clairvoyance](https://github.com/nikitastupin/clairvoyance) that leverages the `extensions` object in `errors` entries from GraphQL's responses to deduce its API schema, rather than parsing error messages. Just like clairvoyance, this allows us to get the target's schema when introspection is disabled.

If your target uses custom error messages that are not commonly seen but has verbose `errors` entries with keywords like `selectionMismatch`, `argumentNotAccepted`, `undefinedField` etc in the `extensions` object, then your target might use graphql-ruby and this fork might be worth a shot!

Just like clairvoyance, it outputs the schema in JSON format, compatible with [GraphQL Voyager](https://github.com/APIs-guru/graphql-voyager), [InQL](https://github.com/doyensec/inql) or [graphql-path-enum](https://gitlab.com/dee-see/graphql-path-enum).

Installation and usage also work the same way, see below.

## Installation

```
$ git clone https://github.com/ovelny/premonition.git
$ cd premonition
$ pip3 install -r requirements.txt
```

## Usage

### From Python interpreter

```
$ python3 -m premonition --help
```

```
$ python3 -m premonition -vv -o /path/to/schema.json -w /path/to/wordlist.txt https://<your-target-path>
```

There is no chance that this fork would exist if I had to create it from scratch: many thanks to [Nikita Stupin](https://github.com/nikitastupin) for open-sourcing clairvoyance and sharing it to everyone.
