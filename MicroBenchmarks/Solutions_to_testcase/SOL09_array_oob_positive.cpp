// Category: Array/Buffer Errors (Success Case)
// Expected Result: Index should be within valid bounds

#include <iostream>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int index = 2;  // SUCCESS: Within valid bounds (0-4)
    
    if (index >= 0 && index < 5) {
        int value = arr[index];
        std::cout << "Value: " << value << std::endl;
    }
    
    return 0;
}
