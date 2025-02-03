package com.sorbonne;

import org.neo4j.graphdb.*;
import org.neo4j.procedure.*;
import java.util.*;
import java.util.stream.Stream;
import org.neo4j.procedure.Mode;
import java.util.Map;
import org.neo4j.graphdb.Result;

public class Neo4jProcedures {
    @Context
    public GraphDatabaseService db;

    private void executeCypher(String query, Object... params) {
        Map<String, Object> parameters = new HashMap<>();
        for (int i = 0; i < params.length - 1; i += 2) {
            parameters.put(String.valueOf(params[i]), params[i + 1]);
        }
        db.executeTransactionally(query, parameters);
    }

    @Procedure(name = "custom.create_network", mode = Mode.WRITE)
    @Description("Crée la structure du réseau de neurones dans Neo4j")
    public void createNetwork(@Name("network_structure") String networkStructure,
                              @Name("task_type") String taskType,
                              @Name("activation") String activation) {
        String query = "CREATE (n:Neuron {structure: $networkStructure, taskType: $taskType, activation: $activation})";
        executeCypher(query, "networkStructure", networkStructure, "taskType", taskType, "activation", activation);
    }

    @Procedure(name = "custom.create_inputs_row_node", mode = Mode.WRITE)
    @Description("Crée les nœuds pour les entrées du réseau")
    public void createInputsRowNode(@Name("network_structure") String networkStructure,
                                    @Name("batch_size") long batchSize) {
        String query = "CREATE (:InputRow {structure: $networkStructure, batchSize: $batchSize})";
        executeCypher(query, "networkStructure", networkStructure, "batchSize", batchSize);
    }

    @Procedure(name = "custom.create_outputs_row_node", mode = Mode.WRITE)
    @Description("Crée les nœuds pour les sorties du réseau")
    public void createOutputsRowNode(@Name("network_structure") String networkStructure,
                                     @Name("batch_size") long batchSize) {
        String query = "CREATE (:OutputRow {structure: $networkStructure, batchSize: $batchSize})";
        executeCypher(query, "networkStructure", networkStructure, "batchSize", batchSize);
    }

    @Procedure(name = "custom.initialize_adam_parameters", mode = Mode.WRITE)
    @Description("Initialise les paramètres Adam du réseau")
    public void initializeAdamParameters() {
        String query = "MATCH (n:Neuron) SET n.momentum = 0.9, n.velocity = 0.999, n.epsilon = 1e-8";
        executeCypher(query);
    }

    @Procedure(name = "custom.set_inputs", mode = Mode.WRITE)
    @Description("Affecte les valeurs des entrées")
    public void setInputs(@Name("dataset") String dataset) {
        String query = "MATCH (i:InputRow) SET i.value = $dataset";
        executeCypher(query, "dataset", dataset);
    }

    @Procedure(name = "custom.set_expected_outputs", mode = Mode.WRITE)
    @Description("Affecte les valeurs de sortie attendues")
    public void setExpectedOutputs(@Name("dataset") String dataset) {
        String query = "MATCH (o:OutputRow) SET o.expectedValue = $dataset";
        executeCypher(query, "dataset", dataset);
    }

    @Procedure(name = "custom.forward_pass", mode = Mode.WRITE)
    @Description("Exécute un passage avant du réseau de neurones")
    public void forwardPass() {
        String query = "MATCH (n:Neuron)-[r:CONNECTS_TO]->(m:Neuron) " +
                "WITH n, r, m, (n.value * r.weight + m.bias) as z " +
                "SET m.value = 1.0 / (1.0 + exp(-z))";
        executeCypher(query);
    }



    @Procedure(name = "custom.compute_loss", mode = Mode.READ)
    @Description("Calcule la perte du réseau")
    public Stream<DoubleResult> computeLoss(@Name("task_type") String taskType) {
        String query = "MATCH (o:OutputRow) RETURN avg((o.value - o.expectedValue)^2) AS loss";
        Map<String, Object> params = new HashMap<>();
        params.put("taskType", taskType);

        return db.executeTransactionally(query, params,
                result -> {
                    if (result.hasNext()) {
                        Map<String, Object> row = result.next();
                        Double loss = (Double) row.get("loss");
                        return Stream.of(new DoubleResult(loss != null ? loss : 0.0));
                    }
                    return Stream.of(new DoubleResult(0.0));
                });
    }

    @Procedure(name = "custom.backward_pass_adam", mode = Mode.WRITE)
    @Description("Effectue la rétropropagation avec Adam")
    public void backwardPassAdam(@Name("learning_rate") double learningRate,
                                 @Name("beta1") double beta1,
                                 @Name("beta2") double beta2,
                                 @Name("epsilon") double epsilon,
                                 @Name("epoch") long epoch) {
        String query = "MATCH (n:Neuron) SET n.weight = n.weight - $learningRate * n.gradient";
        executeCypher(query, "learningRate", learningRate);
    }

    @Procedure(name = "custom.constrain_weights", mode = Mode.WRITE)
    @Description("Contraint les poids des neurones")
    public void constrainWeights() {
        String query = "MATCH (n:Neuron) WHERE n.weight > 1 SET n.weight = 1";
        executeCypher(query);
    }

    public static class DoubleResult {
        public final double value;
        public DoubleResult(double value) { this.value = value; }
    }
}