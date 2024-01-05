from typing import Dict, List

from lightning.pytorch.callbacks import Callback

from relik.reader.data.relik_reader_re_data import RelikREDataset
from relik.reader.data.relik_reader_sample import RelikReaderSample
from relik.reader.relik_reader_predictor import RelikReaderPredictor
from relik.reader.utils.metrics import compute_metrics


class StrongMatching:
    def __call__(self, predicted_samples: List[RelikReaderSample]) -> Dict:
        # accumulators
        correct_predictions, total_predictions, total_gold = (
            0,
            0,
            0,
        )
        correct_predictions_strict, total_predictions_strict = (
            0,
            0,
        )
        correct_predictions_bound, total_predictions_bound = (
            0,
            0,
        )
        correct_span_predictions, total_span_predictions, total_gold_spans = (
            0,
            0,
            0,
        )
        (
            correct_span_in_triplets_predictions,
            total_span_in_triplets_predictions,
            total_gold_spans_in_triplets,
        ) = (
            0,
            0,
            0,
        )

        # collect data from samples
        for sample in predicted_samples:
            if sample.triplets is None:
                sample.triplets = []

            if sample.span_candidates:
                predicted_annotations_strict = set(
                    [
                        (
                            triplet["subject"]["start"],
                            triplet["subject"]["end"],
                            triplet["subject"]["type"],
                            triplet["relation"]["name"],
                            triplet["object"]["start"],
                            triplet["object"]["end"],
                            triplet["object"]["type"],
                        )
                        for triplet in sample.predicted_relations
                    ]
                )
                gold_annotations_strict = set(
                    [
                        (
                            triplet["subject"]["start"],
                            triplet["subject"]["end"],
                            triplet["subject"]["type"],
                            triplet["relation"]["name"],
                            triplet["object"]["start"],
                            triplet["object"]["end"],
                            triplet["object"]["type"],
                        )
                        for triplet in sample.triplets
                    ]
                )
                predicted_spans_strict = set(sample.predicted_entities)
                gold_spans_strict = set(sample.entities)
                predicted_spans_in_triplets = set(
                    [
                        (
                            triplet["subject"]["start"],
                            triplet["subject"]["end"],
                            triplet["subject"]["type"],
                        )
                        for triplet in sample.predicted_relations
                    ]
                    + [
                        (
                            triplet["object"]["start"],
                            triplet["object"]["end"],
                            triplet["object"]["type"],
                        )
                        for triplet in sample.predicted_relations
                    ]
                )
                gold_spans_in_triplets = set(
                    [
                        (
                            triplet["subject"]["start"],
                            triplet["subject"]["end"],
                            triplet["subject"]["type"],
                        )
                        for triplet in sample.triplets
                    ]
                    + [
                        (
                            triplet["object"]["start"],
                            triplet["object"]["end"],
                            triplet["object"]["type"],
                        )
                        for triplet in sample.triplets
                    ]
                )
                # strict
                correct_span_predictions += len(
                    predicted_spans_strict.intersection(gold_spans_strict)
                )
                total_span_predictions += len(predicted_spans_strict)

                correct_span_in_triplets_predictions += len(
                    predicted_spans_in_triplets.intersection(gold_spans_in_triplets)
                )
                total_span_in_triplets_predictions += len(predicted_spans_in_triplets)
                total_gold_spans_in_triplets += len(gold_spans_in_triplets)

                correct_predictions_strict += len(
                    predicted_annotations_strict.intersection(gold_annotations_strict)
                )
                total_predictions_strict += len(predicted_annotations_strict)

            predicted_annotations = set(
                [
                    (
                        triplet["subject"]["start"],
                        triplet["subject"]["end"],
                        -1,
                        triplet["relation"]["name"],
                        triplet["object"]["start"],
                        triplet["object"]["end"],
                        -1,
                    )
                    for triplet in sample.predicted_relations
                ]
            )
            gold_annotations = set(
                [
                    (
                        triplet["subject"]["start"],
                        triplet["subject"]["end"],
                        -1,
                        triplet["relation"]["name"],
                        triplet["object"]["start"],
                        triplet["object"]["end"],
                        -1,
                    )
                    for triplet in sample.triplets
                ]
            )
            predicted_spans = set(
                [(ss, se) for (ss, se, _) in sample.predicted_entities]
            )
            gold_spans = set([(ss, se) for (ss, se, _) in sample.entities])
            total_gold_spans += len(gold_spans)

            correct_predictions_bound += len(predicted_spans.intersection(gold_spans))
            total_predictions_bound += len(predicted_spans)

            total_predictions += len(predicted_annotations)
            total_gold += len(gold_annotations)
            # correct relation extraction
            correct_predictions += len(
                predicted_annotations.intersection(gold_annotations)
            )

        span_precision, span_recall, span_f1 = compute_metrics(
            correct_span_predictions, total_span_predictions, total_gold_spans
        )
        bound_precision, bound_recall, bound_f1 = compute_metrics(
            correct_predictions_bound, total_predictions_bound, total_gold_spans
        )

        precision, recall, f1 = compute_metrics(
            correct_predictions, total_predictions, total_gold
        )

        if sample.span_candidates:
            precision_strict, recall_strict, f1_strict = compute_metrics(
                correct_predictions_strict, total_predictions_strict, total_gold
            )
            (
                span_in_triplet_precisiion,
                span_in_triplet_recall,
                span_in_triplet_f1,
            ) = compute_metrics(
                correct_span_in_triplets_predictions,
                total_span_in_triplets_predictions,
                total_gold_spans_in_triplets,
            )
            return {
                "span-precision-strict": span_precision,
                "span-recall-strict": span_recall,
                "span-f1-strict": span_f1,
                "span-precision": bound_precision,
                "span-recall": bound_recall,
                "span-f1": bound_f1,
                "span-in-triplet-precision": span_in_triplet_precisiion,
                "span-in-triplet-recall": span_in_triplet_recall,
                "span-in-triplet-f1": span_in_triplet_f1,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "precision-strict": precision_strict,
                "recall-strict": recall_strict,
                "f1-strict": f1_strict,
            }
        else:
            return {
                "span-precision": bound_precision,
                "span-recall": bound_recall,
                "span-f1": bound_f1,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }


class REStrongMatchingCallback(Callback):
    def __init__(self, dataset_path: str, dataset_conf) -> None:
        super().__init__()
        self.dataset_path = dataset_path
        self.dataset_conf = dataset_conf
        self.strong_matching_metric = StrongMatching()

    def on_validation_epoch_start(self, trainer, pl_module) -> None:
        dataloader = trainer.val_dataloaders
        if (
            self.dataset_path == dataloader.dataset.dataset_path
            and dataloader.dataset.samples is not None
            and len(dataloader.dataset.samples) > 0
        ):
            relik_reader_predictor = RelikReaderPredictor(
                pl_module.relik_reader_re_model, dataloader=trainer.val_dataloaders
            )
        else:
            relik_reader_predictor = RelikReaderPredictor(
                pl_module.relik_reader_re_model
            )
        predicted_samples = relik_reader_predictor._predict(
            self.dataset_path,
            None,
            self.dataset_conf,
        )
        predicted_samples = list(predicted_samples)
        for sample in predicted_samples:
            RelikREDataset._convert_annotations(sample)
        for k, v in self.strong_matching_metric(predicted_samples).items():
            pl_module.log(f"val_{k}", v)