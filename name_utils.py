from wonderwords import RandomWord
import math
import random


def generateSessionID(seedName=None, seedNumber=None):
    if seedName is None:
        seedName = random.random()
    if seedNumber is None:
        seedNumber = random.random()

    animalNames = [
        "Aardvark", "Albatross", "Alligator", "Alpaca", "Ant", "Anteater", "Antelope", "Ape", "Armadillo",
        "Baboon", "Badger", "Bald Eagle", "Barracuda", "Bear", "Beaver", "Bee", "Beetle", "Bird",
        "Bison", "Boar", "Butterfly", "Camel", "Cat", "Caterpillar", "Chameleon", "Cheetah", "Chicken",
        "Chimpanzee", "Chinchilla", "Chipmunk", "Clam", "Cobra", "Cockroach", "Cod", "Condor", "Cow",
        "Coyote", "Crab", "Crane", "Crocodile", "Crow", "Deer", "Dinosaur", "Dog", "Dolphin", "Donkey",
        "Dove", "Dragonfly", "Duck", "Eagle", "Eel", "Elephant", "Elk", "Emu", "Falcon", "Fish",
        "Flamingo", "Fly", "Fox", "Frog", "Gazelle", "Gecko", "Gerbil", "Giraffe", "Goat", "Goose",
        "Gorilla", "Grasshopper", "Grizzly Bear", "Hamster", "Hare", "Hawk", "Hedgehog", "Hippopotamus",
        "Hornet", "Horse", "Hummingbird", "Hyena", "Iguana", "Impala", "Jackal", "Jaguar", "Jellyfish",
        "Kangaroo", "Kingfisher", "Koala", "Komodo Dragon", "Kookaburra", "Lemur", "Leopard", "Lion",
        "Lizard", "Llama", "Lobster", "Lynx", "Magpie", "Mallard", "Manatee", "Mantis", "Meerkat",
        "Mink", "Mole", "Mongoose", "Monkey", "Moose", "Mosquito", "Moth", "Mouse", "Mule", "Newt",
        "Octopus", "Okapi", "Opossum", "Ostrich", "Otter", "Owl", "Ox", "Panda", "Panther", "Parrot",
        "Peacock", "Pelican", "Penguin", "Pheasant", "Pig", "Pigeon", "Piranha", "Platypus", "Polar Bear",
        "Pony", "Porcupine", "Porpoise", "Puma", "Python", "Quail", "Rabbit", "Raccoon", "Rat", "Raven",
        "Red Panda", "Reindeer", "Rhinoceros", "Roadrunner", "Robin", "Salamander", "Salmon", "Sandpiper",
        "Sardine", "Scorpion", "Seal", "Seahorse", "Shark", "Sheep", "Shrew", "Skunk", "Sloth", "Snail",
        "Snake", "Sparrow", "Spider", "Squid", "Squirrel", "Starfish", "Stingray", "Stork", "Swallow",
        "Swan", "Tapir", "Tarsier", "Tiger", "Toad", "Tortoise", "Toucan", "Turkey", "Turtle", "Walrus",
        "Wasp", "Weasel", "Whale", "Wolf", "Wolverine", "Wombat", "Woodpecker", "Worm", "Yak", "Zebra"
    ]
    randomName = math.floor(seedName * len(animalNames))
    randomNumber = math.floor(seedNumber * 100)
    return (animalNames[randomName], randomNumber)


def coolName(type="guild", seed=True, seedNumber=None):
    r = RandomWord()
    name = None

    if seedNumber is None:
        seedNumber = random.random()
    elif 0 < seedNumber < 1:
        pass
    else:
        seedNumber = 0.5

    randomNumber = math.floor(seedNumber * 100)

    if type == "guild":
        rAdj = r.word(include_categories=["adjectives"])
        rNoun = r.word(include_categories=["nouns"])
        name = f"{rAdj.capitalize()}{rNoun.capitalize()}"

    if type == "action":
        randNoun = r.word(include_categories=["nouns"], word_max_length=6)
        randVerb = r.word(include_categories=["verbs"], word_min_length=8)
        name = f"{randNoun.capitalize()}{randVerb.capitalize()}"

    if seed is True:
        return f"{name}{randomNumber}"

    return name
