import { useState } from 'react';
import { ApolloClient, InMemoryCache, gql, useLazyQuery } from '@apollo/client';
import TenderDashboard from './TenderDashboard';
import Sidebar from './Sidebar';

const client = new ApolloClient({
  uri: 'http://localhost:8001/graphql',
  cache: new InMemoryCache(),
});

const ASK_AGENT = gql`
  query AskAgent($question: String!) {
    askAgent(question: $question) {
      answer
      matches {
        title
        contractingAuthority
        summary
        url
        referenceNumber
        submissionDeadline
        sector
        estimatedValue
        fitTier
        fitReasons {
          criterion
          status
          reason
        }
      }
    }
  }
`;

function App() {
  const [tenders, setTenders] = useState([]);
  const [agentAnswer, setAgentAnswer] = useState("");

  const [askAgent, { loading }] = useLazyQuery(ASK_AGENT, {
    client,
    onCompleted: (data) => {
      setTenders(data.askAgent.matches);
      setAgentAnswer(data.askAgent.answer);
    },
  });

  return (
  <div style={{ display: 'flex', height: '100vh', width: '100vw' }}>
    <Sidebar 
      onSearch={(q) => askAgent({ variables: { question: q } })} 
      answer={agentAnswer}
      tenders={tenders}
      loading={loading}
    />
    <TenderDashboard tenders={tenders} />
  </div>
);
}

export default App;