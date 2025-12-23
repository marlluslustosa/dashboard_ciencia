PESOS = {
    "A1": 100, "A2": 85, "A3": 75, "A4": 65,
    "B1": 55,  "B2": 40, "B3": 25, "B4": 10
}

GRUPOS_RAW = {
    "Avaliação Educacional (NAVE)": ["Adriana Eufrásio Braga", "Marcos Antonio Martins Lima", "Maria Isabel Filgueiras Lima Ciasca", "Tania Vicente Viana", "Wagner Bandeira Andriola"],
    "Educação, Currículo e Ensino (LECE)": ["Bernadete De Souza Porto", "Cassandra Ribeiro Joye", "Eduardo Santos Junqueira Rodrigues", "Elvis De Azevedo Matos", "Gilberto Santos Cerqueira", "Herminio Borges Neto", "Jorge Carvalho Brandão", "José Aires De Castro Filho", "Juscileide Braga De Castro", "Luis Távora Furtado Ribeiro", "Luiz Botelho Albuquerque", "Marco Antônio Toledo Nascimento", "Maria José Costa Dos Santos", "Paulo Meireles Barguil", "Pedro Rogério", "Raphael Alves Feitosa", "Raquel Crosara Maia Leite"],
    "Educação, Estética e Sociedade": ["Angela Maria Bessa Linhares", "Francisca Maurilene Do Carmo", "Josefa Jackline Rabelo", "Maria Das Dores Mendes Segundo", "Osterne Nonato Maia Filho", "Valdemarin Coelho Gomes"],
    "Humanidades e Educação (HUMEDUC)": ["Alcides Fernando Gussi", "Antonia Lis De Maria Martins Torres", "Eduardo Ferreira Chagas", "Gisafran Nazareno Mota Jucá", "Hildemar Luiz Rech", "Pablo Severiano Benevides", "Patrícia Helena Carvalho Holanda"],
    "História e Memória da Educação (NHIME)": ["Adauto Lopes Da Silva Filho", "Fátima Maria Nobre Lopes", "Francisco Ari De Andrade", "José Gerardo Vasconcelos", "Luis Távora Furtado Ribeiro"],
    "Linguagens e Práticas Educativas (LIPED)": ["Adriana Leite Limaverde Gomes", "Bernadete De Souza Porto", "Francisca Geny Lustosa", "Rosimeire Costa De Andrade Cruz", "Silvia Helena Vieira Cruz"],
    "Movimentos Sociais, Educação Popular e Escola (MOSEP)": ["Henrique Antunes Cunha Junior", "João Batista De Albuquerque Figueiredo", "Maria Eleni Henrique Da Silva", "Sandra Haydée Petit"],
    "Trabalho e Educação (LTE)": ["Antonia Rozimar Machado E Rocha", "Clarice Zientarski", "Hildemar Luiz Rech", "Justino De Sousa Junior"]
}

# Compreensão de lista para limpar espaços
GRUPOS_PESQUISA = {k: [p.strip() for p in v] for k, v in GRUPOS_RAW.items()}
