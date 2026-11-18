# API de Atividades da Mergington High School

Uma aplicação FastAPI super simples que permite aos estudantes visualizar e se inscrever em atividades extracurriculares.

## Funcionalidades

- Visualizar todas as atividades extracurriculares disponíveis
- Inscrever-se em atividades

## Primeiros Passos

1. Instale as dependências:

   ```
   pip install fastapi uvicorn
   ```

2. Execute a aplicação:

   ```
   python app.py
   ```

3. Abra seu navegador e vá para:
   - Documentação da API: http://localhost:8000/docs
   - Documentação alternativa: http://localhost:8000/redoc

## Endpoints da API

| Método | Endpoint                                                          | Descrição                                                           |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Obter todas as atividades com seus detalhes e contagem atual de participantes |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Inscrever-se em uma atividade                                       |

## Modelo de Dados

A aplicação usa um modelo de dados simples com identificadores significativos:

1. **Atividades** - Usa o nome da atividade como identificador:

   - Descrição
   - Cronograma
   - Número máximo de participantes permitidos
   - Lista de emails de estudantes que estão inscritos

2. **Estudantes** - Usa email como identificador:
   - Nome
   - Nível da série

Todos os dados são armazenados na memória, o que significa que os dados serão resetados quando o servidor reiniciar.

## Contas de Professores

Estudantes podem visualizar atividades e participantes. Somente professores autenticados podem registrar ou remover estudantes. As contas dos professores ficam em `teachers.json`; as senhas são armazenadas como hashes PBKDF2 com salt, não em texto simples.

Para criar uma senha, execute este comando no terminal e informe a senha quando solicitado:

```sh
python -c 'import getpass, hashlib, secrets; salt = secrets.token_bytes(16); password = getpass.getpass("Teacher password: "); digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000); print("salt=" + salt.hex()); print("password_hash=" + digest.hex())'
```

Adicione os valores gerados a `teachers.json` neste formato:

```json
{
  "teachers": [
    {
      "username": "teacher1",
      "salt": "generated-salt",
      "password_hash": "generated-password-hash"
    }
  ]
}
```

As sessões de professor expiram após oito horas e são mantidas em memória; reiniciar o servidor encerra as sessões ativas.
