from random import randint

# paramètres
start = 63
objectif = 20
nb_tests = 1000


results = []


for i in range(nb_tests):
    nstart = start
    pari = 1

    while nstart > 0 and nstart < objectif + start:
        if randint(0, 100) < 48:
            nstart += pari
            pari = 1
        else:
            if nstart < pari:
                pari = nstart
            nstart -= pari
            pari *=2

    print("result:", nstart, " €", end="")
    if nstart >= objectif + start:
        print(" - ✓")
        results.append(True)
    else:
        print(" - ✗")
        results.append(False)


success_ratio = sum(results) / len(results)
print(f"Ratio de réussite : {success_ratio:.2%}")

print(f"Départ : {start*nb_tests} €")
print(f"Objectif : {(start+objectif)*sum(results)} €")