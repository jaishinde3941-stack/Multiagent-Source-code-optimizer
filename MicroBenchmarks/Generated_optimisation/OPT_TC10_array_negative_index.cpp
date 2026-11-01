#include <iostream>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int index = -1;

    if (index >= 0 && index < sizeof(arr) / sizeof(arr[0])) {
        int value = arr[index];  // Safe access
        std::cout << "Value: " << value << std::endl;
    } else {
        std::cerr << "Error: Index out of bounds" << std::endl;
    }

    return 0;
}