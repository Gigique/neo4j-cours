package com.sorbonne;

import org.neo4j.graphdb.GraphDatabaseService;
import org.neo4j.graphdb.Transaction;
import org.neo4j.logging.Log;
import org.neo4j.procedure.*;

import java.util.Map;
import java.util.stream.Stream;


public class CreateNeuronGraph {
    // This gives us a log instance that outputs messages to the
    // standard log, normally found under `data/log/console.log`
    @Context
    public Log log;
    @Context
    public GraphDatabaseService db;


    // Exemple de base à lire completer corriger
    // Pour utiliser call nn.createNeuron("123","0","input","sotfmax")
    @Procedure(name = "nn.createNeuronGraph",mode = Mode.WRITE)
    @Description("")
    public Stream<CreateResult> createNeuron(@Name("id1") String id1,
                                             @Name("id2") String id2,
                                             @Name("id3") String id3)
    {
        try (Transaction tx = db.beginTx()) {
            // Créer 3 neurones
            tx.execute("CREATE (n1:Neuron {id: $id1, layer: 0, type: 'input', activation_function: 'relu'})",
                    Map.of("id1", id1));
            tx.execute("CREATE (n2:Neuron {id: $id2, layer: 1, type: 'hidden', activation_function: 'sigmoid'})",
                    Map.of("id2", id2));
            tx.execute("CREATE (n3:Neuron {id: $id3, layer: 2, type: 'output', activation_function: 'softmax'})",
                    Map.of("id3", id3));

            // Ajouter les connexions entre les neurones
            tx.execute("MATCH (n1:Neuron {id: $id1}), (n2:Neuron {id: $id2}) " +
                    "CREATE (n1)-[:CONNECTED_TO]->(n2)", Map.of("id1", id1, "id2", id2));

            tx.execute("MATCH (n2:Neuron {id: $id2}), (n3:Neuron {id: $id3}) " +
                    "CREATE (n2)-[:CONNECTED_TO]->(n3)", Map.of("id2", id2, "id3", id3));

            tx.commit();
            return Stream.of(new CreateResult("Neurons created and connected successfully!"));
        } catch (Exception e) {
            log.error("Error creating neurons", e);
            return Stream.of(new CreateResult("Error creating neurons"));
        }
    }

    public static class CreateResult {
        public final String result;
        public CreateResult(String result) {
            this.result = result;
        }
    }
}